import logging

import numpy as np
import cv2
import slicer.util
import vtk
import slicer

try:
    import ruptures as rpt
except:
    pip_install('ruptures')
    import ruptures as rpt

import vtkmodules.vtkCommonCore
from typing import List

import SegmentStatistics
from .utils import (
    normalize,
    getRASFromIjk,
    getIjkFromRAS,
    createLineIterator
)

import inspect
from vtkmodules.vtkCommonDataModel import (
    vtkVector3d,
    vtkImageData
)
from MRMLCorePython import vtkMRMLTableNode
from SegmentEditor import SegmentEditorWidget
from MRMLCorePython import (
    vtkMRMLSegmentationNode,
    vtkMRMLVolumeNode,
    vtkMRMLScalarVolumeNode,
    vtkMRMLScene,
    vtkMRMLModelNode,
    vtkMRMLTransformNode,
    vtkMRMLSubjectHierarchyNode
)
from vtkSegmentationCore import (
    vtkSegmentation,
    vtkSegment,
    vtkOrientedImageData
)
from vtkSlicerMarkupsModuleMRMLPython import (
    vtkMRMLMarkupsLineNode,
    vtkMRMLMarkupsCurveNode,
    vtkMRMLMarkupsFiducialNode
)
from vtkSlicerSegmentationsModuleMRMLPython import (
    vtkMRMLSegmentEditorNode
)
from SegmentEditor import SegmentEditorWidget
from SegmentEditorEffects import (
    AbstractScriptedSegmentEditorEffect,
    SegmentEditorThresholdEffect,
    SegmentEditorMarginEffect,
    SegmentEditorIslandsEffect
)
import SegmentEditorEffects


class CalculatorVolume:
    def __init__(self, applierLogic, defaultAutothresholdMethod, defaultPreviewState: bool):
        self.isPreviewState = defaultPreviewState
        self.segmentEditorWidget = None
        self.segmentEditorNode: vtkMRMLSegmentEditorNode = None
        self.applierLogic = applierLogic
        self.offsetThreshold = 0.0
        self.maximumThreshold = 0.0
        self.autoThresholdMethod = defaultAutothresholdMethod
        self.segmentName: str = None
        self.volumeNode: vtkMRMLVolumeNode = None
        self.segmentationNode: vtkMRMLSegmentationNode = None
        self.axisNames = ["Axial", "Coronal", "Sagittal"]
        self.currentAxis = 0

    @staticmethod
    def getNameResultsFolder():
        return "Ruptures"

    def getResultsFolder(self, shNode):
        if self.segmentationNode is None:
            return 0

        segmentationHierarchyID = shNode.GetItemByDataNode(self.segmentationNode)
        if segmentationHierarchyID == 0:
            return 0
        return shNode.GetItemChildWithName(segmentationHierarchyID, self.getNameResultsFolder())

    def clearBoneContinuityResults(self):
        if self.volumeNode is None or self.segmentationNode is None:
            return
        shNode: vtkMRMLSubjectHierarchyNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        folder = self.getResultsFolder(shNode)
        if folder != 0:
            shNode.RemoveItem(folder)

    def changeAxis(self, axis):
        shNode: vtkMRMLSubjectHierarchyNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        rupturesFolder = self.getResultsFolder(shNode)
        if rupturesFolder == 0:
            return

        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        folderPlugin = pluginHandler.pluginByName("Folder")

        axisFolder = shNode.GetItemChildWithName(rupturesFolder, self.axisNames[self.currentAxis])
        if axisFolder != 0:
            folderPlugin.setDisplayVisibility(axisFolder, 0)

        self.currentAxis = axis

        axisFolder = shNode.GetItemChildWithName(rupturesFolder, self.axisNames[self.currentAxis])
        if axisFolder != 0:
            folderPlugin.setDisplayVisibility(axisFolder, 1)

    def boneContinuityTest(self):
        from scipy.ndimage import (
            maximum_filter,
            median_filter,
            uniform_filter
        )

        LENGTH_BACK_CHECK_NORMAL = 0.1
        LENGTH_FORWARD_CHECK_NORMAL = 3.8

        MIN_SIZE = 30
        STEP_VISUALIZE_RUPTURE = 5

        THRESHOLD_FOR_LOWER_RUPTURE = 75
        UPPER_THRESHOLD = 400

        shNode: vtkMRMLSubjectHierarchyNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        axis = self.currentAxis

        with (slicer.util.tryWithErrorDisplay("Failed bone continuity test", waitCursor=True)):
            image = slicer.util.arrayFromVolume(self.volumeNode)

            segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
            segmentId = segmentation.GetSegmentIdBySegmentName(self.segmentName)
            segmentArray = slicer.util.arrayFromSegmentBinaryLabelmap(self.segmentationNode, segmentId, self.volumeNode)

            directionMatrix = np.zeros((3, 3))
            self.volumeNode.GetIJKToRASDirections(directionMatrix)
            multiplier = directionMatrix[2 - axis]

            if multiplier[0] != 0:
                image = np.moveaxis(image, 2, 0)
                segmentArray = np.moveaxis(segmentArray, 2, 0)
            elif multiplier[1] != 0:
                image = np.moveaxis(image, 0, 1)
                segmentArray = np.moveaxis(segmentArray, 0, 1)

            vectorForCross = np.zeros(3)
            vectorForCross[2 - axis] = -1 if axis == 1 else 1

            rupturesFolderName = self.getNameResultsFolder()
            axisFolderName = self.axisNames[axis]

            segmentationHierarchyID = shNode.GetItemByDataNode(self.segmentationNode)
            rupturesFolder = self.getResultsFolder(shNode)
            if rupturesFolder == 0:
                rupturesFolder = shNode.CreateFolderItem(segmentationHierarchyID, rupturesFolderName)

            axisFolder = shNode.GetItemChildWithName(rupturesFolder, axisFolderName)
            if axisFolder == 0:
                axisFolder = shNode.CreateFolderItem(rupturesFolder, axisFolderName)
            else:
                shNode.RemoveItemChildren(axisFolder)

            HALF_COUNT_NEIGHBOURS = 4

            class PointInfo:
                def __init__(self, pointRas, maxIntensity):
                    self.pointRas = pointRas
                    self.maxIntensity = maxIntensity

            overallPointsInfo = np.empty(segmentArray.shape[0], dtype=np.ndarray)
            for segmentIndex, segment in enumerate(segmentArray):
                mask = np.where(segment > 0, np.array(1, dtype=np.uint8), np.array(0, dtype=np.uint8))
                contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
                segmentImage = image[segmentIndex]
                segmentImage = maximum_filter(segmentImage, size=1)
                segmentImage = uniform_filter(segmentImage, size=2)

                contoursPointsInfo = []
                for contourIndex, contour in enumerate(contours):
                    contourSize = len(contour)
                    if contourSize <= HALF_COUNT_NEIGHBOURS * 2 + 1 or contourSize <= MIN_SIZE * 2:
                        continue

                    def getRASFromIJKByAxis(x):
                        ijk = np.empty(3)
                        m = 0
                        for i, coef in enumerate(multiplier):
                            if coef == 0:
                                ijk[i] = x[m]
                                m += 1
                            else:
                                ijk[i] = segmentIndex
                        return getRASFromIjk(self.volumeNode, ijk)

                    contourInRas = np.array([getRASFromIJKByAxis(x[0]) for x in contour])

                    area = cv2.contourArea(contour, True)
                    if area == 0:
                        x1, y1 = contour[0][0]
                        x2, y2 = contour[1][0]
                        if x2 == x1:
                            sign = np.sign(y2 - y1)
                        elif y2 == y1:
                            sign = np.sign(x2 - x1)
                        else:
                            sign = np.sign((y2 - y1) / (x2 - x1))
                    else:
                        sign = np.sign(area)
                    normals_by_cross = np.array([normalize(np.cross(
                        vectorForCross * -sign,
                        contourInRas[i + 1 if i < contourSize - 1 else 0] - contourInRas[i]
                    )) for i in range(contourSize)])

                    normals = np.empty_like(normals_by_cross)
                    for i in range(contourSize):
                        neighbours = np.empty((HALF_COUNT_NEIGHBOURS * 2 + 1, 3))
                        all_indices = (i - np.arange(HALF_COUNT_NEIGHBOURS, -HALF_COUNT_NEIGHBOURS - 1,
                                                     -1)) % contourSize
                        neighbours[:] = normals_by_cross[all_indices]

                        average_direction = np.mean(neighbours, axis=0)
                        normals[i] = normalize(average_direction)

                    maxIntensities = np.empty(contourSize, dtype=tuple)
                    for i in range(contourSize):
                        pointRas = contourInRas[i]
                        normalRas = normals[i]

                        backRasPoint = pointRas - normalRas * LENGTH_BACK_CHECK_NORMAL
                        forwardRasPoint = pointRas + normalRas * LENGTH_FORWARD_CHECK_NORMAL

                        def cutIJKCoordsByAxis(x):
                            result = np.empty(2, dtype=np.int64)
                            offset = 0
                            for i, coef in enumerate(multiplier):
                                if coef == 0:
                                    result[i - offset] = x[i]
                                else:
                                    offset += 1
                            return result

                        backIjkPoint = cutIJKCoordsByAxis(getIjkFromRAS(self.volumeNode, backRasPoint))
                        forwardIjkPoint = cutIJKCoordsByAxis(getIjkFromRAS(self.volumeNode, forwardRasPoint))

                        linePoints = createLineIterator(backIjkPoint, forwardIjkPoint, segmentImage)
                        maxIndex = np.argmax(linePoints[:, 2], axis=0)

                        maxPoint = linePoints[maxIndex]
                        maxIntensities[i] = PointInfo(pointRas, maxPoint[2])

                    contoursPointsInfo.append(maxIntensities)
                overallPointsInfo[segmentIndex] = np.array(contoursPointsInfo, dtype=np.ndarray)

            getterIntensity = np.vectorize(lambda point: point.maxIntensity)

            flatMaxIntensities = getterIntensity(np.concatenate(
                [x.flatten() if isinstance(x, np.ndarray) else np.array([x]) for x in np.concatenate(
                    [x.flatten() if isinstance(x, np.ndarray) else np.array([x]) for x in overallPointsInfo])]))
            upperThreshold = max(np.median(flatMaxIntensities), UPPER_THRESHOLD)
            for segmentIndex in range(len(segmentArray)):
                contourFolder = None

                for contourIndex, contour in enumerate(overallPointsInfo[segmentIndex]):
                    maxIntensities = getterIntensity(overallPointsInfo[segmentIndex][contourIndex])
                    maxIntensities = np.where(maxIntensities > upperThreshold, upperThreshold, maxIntensities)
                    pointsInfo = overallPointsInfo[segmentIndex][contourIndex]

                    algo = rpt.KernelCPD(kernel="linear", min_size=MIN_SIZE).fit(maxIntensities)

                    bkps = algo.predict(pen=15000)
                    bkps.insert(0, 0)

                    # At the end of bkps there is always the length of the original array
                    bkps[len(bkps) - 1] -= 1

                    def visualize(indexInBkps):
                        nonlocal contourFolder
                        startIndex = bkps[indexInBkps]
                        endIndex = bkps[indexInBkps + 1]

                        curveNode: vtkMRMLMarkupsCurveNode = slicer.mrmlScene.AddNewNodeByClass(
                            "vtkMRMLMarkupsCurveNode", str(startIndex) + "-" + str(endIndex))
                        if contourFolder is None:
                            contourFolder = shNode.CreateFolderItem(axisFolder, f'{segmentIndex}')
                        shNode.SetItemParent(shNode.GetItemByDataNode(curveNode), contourFolder)

                        def addPoint(m):
                            pointRas = pointsInfo[m].pointRas
                            curveNode.AddControlPointWorld(vtkVector3d(pointRas[0], pointRas[1], pointRas[2]), str(m))
                            curveNode.SetNthControlPointLocked(curveNode.GetNumberOfControlPoints() - 1, True)

                        addPoint(startIndex)
                        for j in range(startIndex + STEP_VISUALIZE_RUPTURE, endIndex - STEP_VISUALIZE_RUPTURE,
                                       STEP_VISUALIZE_RUPTURE):
                            addPoint(j)
                        addPoint(endIndex)

                    for i in range(0, len(bkps) - 1):
                        startIndex = bkps[i]
                        endIndex = bkps[i + 1]

                        ruptureIntensities = maxIntensities[startIndex:endIndex]
                        index = int(len(ruptureIntensities) * 0.1)
                        sortedIntensities = np.sort(ruptureIntensities)
                        meanInRuptureRange = np.mean(sortedIntensities[index:-index])
                        # print("Mean in " + str(startIndex) + "-" + str(endIndex) + ": " + str(meanInRuptureRange))
                        if meanInRuptureRange < THRESHOLD_FOR_LOWER_RUPTURE:
                            visualize(i)

                    # print(np.array2string(maxIntensities, separator=","))
                # break

    def enter(self):
        self.segmentEditorWidget = slicer.qMRMLSegmentEditorWidget()
        self.segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        self.segmentEditorNode: vtkMRMLSegmentEditorNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentEditorNode"
        )
        self.tryChangeStateTool()

    def exit(self):
        self.turnOffEffect()
        slicer.mrmlScene.RemoveNode(self.segmentEditorNode)
        self.tryRemoveEmptySegment()
        self.segmentEditorNode = None
        self.segmentEditorWidget = None

    def setIsPreviewState(self, newState):
        self.isPreviewState = newState
        self.tryChangeStateTool()

    def setOffsetThreshold(self, offsetThreshold: float):
        self.offsetThreshold = offsetThreshold
        if self.isActiveEffect():
            self.updateEffectParameters()

    def setAutoThresholdMethod(self, method):
        self.autoThresholdMethod = method
        if self.isActiveEffect():
            self.updateEffect()

    def setSegmentName(self, segmentName: str):
        if self.segmentationNode is not None:
            segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
            currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
            if currentSegmentID != "":
                isEmptySegment = slicer.util.arrayFromSegmentBinaryLabelmap(self.segmentationNode, currentSegmentID,
                                                                            self.volumeNode).max() == 0
                if isEmptySegment:
                    segmentation.GetSegment(currentSegmentID).SetName(segmentName)
        # All the ways to take a field name for this constant seemed too expensive to me
        self.changeParameter('segmentName', segmentName, self.updateSegment)

    def setVolumeNode(self, volumeNode: vtkMRMLVolumeNode) -> None:
        self.volumeNode = volumeNode
        if self.segmentationNode is not None:
            self.segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

        # I do this in order to completely refresh the entire view, since I’m not sure that it will work otherwise
        self.turnOffEffect()
        self.tryChangeStateTool()

    def tryRemoveEmptySegment(self):
        if self.segmentationNode is not None:
            segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
            currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
            if currentSegmentID != "":
                isEmptySegment = slicer.util.arrayFromSegmentBinaryLabelmap(self.segmentationNode, currentSegmentID,
                                                                            self.volumeNode).max() == 0
                if isEmptySegment:
                    segmentation.RemoveSegment(currentSegmentID)

    def setSegmentationNode(self, segmentationNode: vtkMRMLSegmentationNode) -> None:
        self.tryRemoveEmptySegment()

        shNode: vtkMRMLSubjectHierarchyNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        folderPlugin = pluginHandler.pluginByName("Folder")

        rupturesFolder = self.getResultsFolder(shNode)
        if rupturesFolder != 0:
            folderPlugin.setDisplayVisibility(rupturesFolder, 0)

        self.segmentationNode = segmentationNode
        if self.segmentationNode is not None:
            volumeNodeRefWithSegmentationNode = segmentationNode.GetNodeReference(
                segmentationNode.GetReferenceImageGeometryReferenceRole()
            )
            if volumeNodeRefWithSegmentationNode is None:
                if self.volumeNode is not None:
                    segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(self.volumeNode)
            else:
                self.volumeNode = volumeNodeRefWithSegmentationNode

        rupturesFolder = self.getResultsFolder(shNode)
        if rupturesFolder != 0:
            folderPlugin.setDisplayVisibility(rupturesFolder, 1)

        # I do this in order to completely refresh the entire view, since I’m not sure that it will work otherwise
        self.turnOffEffect()
        self.tryChangeStateTool()

    def changeParameter(self, attributeName, value, callbackChangeFromTrueToTrueStateEffect) -> None:
        oldStateEffect = self.isActiveEffect()
        setattr(self, attributeName, value)
        newStateEffect = self.isActiveEffect()

        if oldStateEffect:
            if newStateEffect:
                callbackChangeFromTrueToTrueStateEffect()
            else:
                self.turnOffEffect()
        elif newStateEffect:
            self.activateEffect()

    def tryChangeStateTool(self):
        if self.isActiveEffect():
            self.activateEffect()
        else:
            self.turnOffEffect()

    def activateEffect(self):
        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.segmentationNode)
        self.segmentEditorWidget.setSourceVolumeNode(self.volumeNode)

        self.updateSegment()
        self.setCustomEditorEffect()
        self.updateEffect()

        def applyTool(ijkPoints):
            self.segmentEditorWidget.setActiveEffectByName(None)

            currentSegmentID = self.segmentEditorNode.GetSelectedSegmentID()
            segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
            currentSegment: vtkSegment = segmentation.GetSegment(currentSegmentID)

            # It seems there is no other way
            segmentColor = currentSegment.GetColor()
            segmentation.RemoveSegment(currentSegmentID)
            segmentation.AddEmptySegment(currentSegmentID, self.segmentName, segmentColor)
            self.segmentEditorNode.SetSelectedSegmentID(currentSegmentID)

            self.applierLogic.apply(self, ijkPoints)
            self.tryChangeStateTool()

        effect = self.segmentEditorWidget.activeEffect()
        effect.self().setApplyLogic(applyTool)

    def setCustomEditorEffect(self):
        self.segmentEditorWidget.setActiveEffectByName('Selecting Closed Surface')

    def updateSegment(self):
        segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
        currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
        if currentSegmentID == "":
            currentSegmentID = segmentation.AddEmptySegment(self.segmentName, self.segmentName)
        self.segmentationNode.Modified()
        self.segmentEditorNode.SetSelectedSegmentID(currentSegmentID)
        self.segmentEditorNode.Modified()

    def updateEffect(self):
        effect = self.segmentEditorWidget.activeEffect()
        effect.self().autoThreshold(self.autoThresholdMethod, SegmentEditorEffects.MODE_SET_MIN_UPPER)
        self.maximumThreshold = effect.doubleParameter("MaximumThreshold")
        self.updateEffectParameters()

    def updateEffectParameters(self):
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("MaximumThreshold", self.maximumThreshold + self.offsetThreshold)

    def isActiveEffect(self):
        return self.segmentEditorWidget is not None and self.isPreviewState and self.volumeNode is not None \
            and self.segmentationNode is not None and self.segmentName is not None and self.segmentName != ""

    def turnOffEffect(self):
        if self.segmentEditorWidget is None:
            return
        self.segmentEditorWidget.setActiveEffectByName(None)
        self.segmentEditorWidget.setMRMLSegmentEditorNode(None)
        self.segmentEditorWidget.setSegmentationNode(None)
        self.segmentEditorWidget.setSourceVolumeNode(None)

    def saveResultsToTable(self, tableNode: vtkMRMLTableNode):
        if self.segmentationNode is None:
            raise ValueError("Segmentation node not selected")
        if tableNode is None:
            raise ValueError("Table node not selected")
        if self.segmentationNode.GetSegmentation().GetNumberOfSegments() == 0:
            raise ValueError("Segmentation node has zero number of segments")

        statisticsLogic: SegmentStatisticsLogic = SegmentStatistics.SegmentStatisticsLogic()
        statisticsLogic.getParameterNode().SetParameter("Segmentation", self.segmentationNode.GetID())
        statisticsLogic.computeStatistics()
        statisticsLogic.exportToTable(tableNode, nonEmptyKeysOnly=True)
