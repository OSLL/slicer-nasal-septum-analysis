import logging

import vtk
import slicer
from typing import List

import SegmentStatistics
import inspect
from MRMLCorePython import vtkMRMLTableNode
from SegmentEditor import SegmentEditorWidget
from MRMLCorePython import (
    vtkMRMLSegmentationNode,
    vtkMRMLVolumeNode,
    vtkMRMLScalarVolumeNode,
    vtkMRMLScene
)
from vtkSegmentationCore import (
    vtkSegmentation,
    vtkSegment
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
    def __init__(self, applierLogic, defaultAutothresholdMethod):
        self.isPreviewState = True
        self.segmentEditorWidget = None
        self.segmentEditorNode = None
        self.applierLogic = applierLogic
        self.offsetThreshold = 0.0
        self.maximumThreshold = 0.0
        self.autoThresholdMethod = defaultAutothresholdMethod
        self.segmentName = None
        self.volumeNode = None
        self.segmentationNode = None

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
        self.segmentEditorNode = None
        self.segmentEditorWidget = None

    def setIsPreviewState(self, newState):
        self.isPreviewState = newState
        self.tryChangeStateTool()

    def setOffsetThreshold(self, offsetThreshold: float):
        self.offsetThreshold = offsetThreshold
        if self.isActiveEffect():
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("MaximumThreshold", self.maximumThreshold + self.offsetThreshold)

    def setAutoThresholdMethod(self, method):
        self.autoThresholdMethod = method
        if self.isActiveEffect():
            effect = self.segmentEditorWidget.activeEffect()
            effect.self().autoThreshold(self.autoThresholdMethod, SegmentEditorEffects.MODE_SET_MIN_UPPER)
            self.maximumThreshold = effect.doubleParameter("MaximumThreshold")
            effect.setParameter("MaximumThreshold", self.maximumThreshold + self.offsetThreshold)

    def setSegmentName(self, segmentName: str):
        # TODO: не нашёл способа как взять имя поля
        self.changeParameter('segmentName', segmentName, self.updateSegment)

    def setVolumeNode(self, volumeNode: vtkMRMLScalarVolumeNode) -> None:
        self.changeParameter('volumeNode', volumeNode,
                             lambda: self.segmentEditorWidget.setSourceVolumeNode(self.volumeNode))

    # TODO: Failed to compute threshold value using method KittlerIllingworth
    def setSegmentationNode(self, segmentationNode: vtkMRMLSegmentationNode) -> None:
        def onUpdateSegmentationNode():
            volumeNodeRefWithSegmentationNode = segmentationNode.GetNodeReference(
                segmentationNode.GetReferenceImageGeometryReferenceRole()
            )
            if volumeNodeRefWithSegmentationNode != self.volumeNode:
                self.updateEffect()

            self.updateSegment()

        self.changeParameter('segmentationNode', segmentationNode, onUpdateSegmentationNode)

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
        if not self.isActiveEffect():
            self.turnOffEffect()
            return

        self.activateEffect()

    def activateEffect(self):
        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.segmentationNode)
        self.segmentEditorWidget.setSourceVolumeNode(self.volumeNode)

        self.segmentEditorWidget.setActiveEffectByName("Selecting Closed Surface")
        effect = self.segmentEditorWidget.activeEffect()
        effect.setParameter("SegmentationAlgorithm", "GrowCut")

        self.updateEffect()
        self.updateSegment()

        def applyTool(ijkPoints):
            # TODO: разобраться почему я не могу делать по-другому, и если уверен, что не могу по-другому,
            #  то нужно цвет копировать хотя бы
            currentSegmentID = self.segmentEditorNode.GetSelectedSegmentID()

            segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
            segmentation.RemoveSegment(currentSegmentID)
            segmentation.AddEmptySegment(currentSegmentID)
            self.segmentEditorNode.SetSelectedSegmentID(currentSegmentID)

            self.applierLogic.apply(self, ijkPoints)

            self.segmentationNode.CreateClosedSurfaceRepresentation()
            self.tryChangeStateTool()

        effect.self().setApplyLogic(applyTool)

    def updateEffect(self):
        effect = self.segmentEditorWidget.activeEffect()
        effect.self().autoThreshold(self.autoThresholdMethod, SegmentEditorEffects.MODE_SET_MIN_UPPER)
        self.maximumThreshold = effect.doubleParameter("MaximumThreshold")
        effect.setParameter("MaximumThreshold", self.maximumThreshold + self.offsetThreshold)

    def updateSegment(self):
        segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
        currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
        if currentSegmentID == "" or currentSegmentID is None:
            currentSegmentID = segmentation.AddEmptySegment(self.segmentName, self.segmentName)
        self.segmentEditorNode.SetSelectedSegmentID(currentSegmentID)

    def isActiveEffect(self):
        return self.isPreviewState and self.volumeNode is not None and self.segmentationNode is not None \
            and self.segmentName is not None and self.segmentName != ""

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

        self.segmentationNode.CreateClosedSurfaceRepresentation()

        statisticsLogic: SegmentStatisticsLogic = SegmentStatistics.SegmentStatisticsLogic()
        statisticsLogic.getParameterNode().SetParameter("Segmentation", self.segmentationNode.GetID())
        statisticsLogic.computeStatistics()
        statisticsLogic.exportToTable(tableNode, nonEmptyKeysOnly=True)
