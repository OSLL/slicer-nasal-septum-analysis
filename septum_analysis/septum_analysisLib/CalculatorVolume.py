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
        self.segmentEditorNode: vtkMRMLSegmentEditorNode = None
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
            self.updateEffectParameters()

    def setAutoThresholdMethod(self, method):
        self.autoThresholdMethod = method
        if self.isActiveEffect():
            self.updateEffect()

    def setSegmentName(self, segmentName: str):
        # All the ways to take a field name by a written attribute seemed too expensive to me
        self.changeParameter('segmentName', segmentName, self.updateSegment)

    def setVolumeNode(self, volumeNode: vtkMRMLScalarVolumeNode) -> None:
        self.volumeNode = volumeNode
        if self.segmentationNode is not None:
            self.segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)
        self.turnOffEffect()
        # TODO: you need to think about how to make it more optimized without bugs.
        #  Also, this doesn’t always work either.
        self.tryChangeStateTool()

    def setSegmentationNode(self, segmentationNode: vtkMRMLSegmentationNode) -> None:
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

        self.turnOffEffect()
        # TODO: you need to think about how to make it more optimized without bugs
        #  Also, this doesn’t always work either.
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
        self.segmentEditorWidget.setActiveEffectByName("Selecting Closed Surface")

    def updateSegment(self):
        segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
        currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
        if currentSegmentID == "" or currentSegmentID is None:
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

        statisticsLogic: SegmentStatisticsLogic = SegmentStatistics.SegmentStatisticsLogic()
        statisticsLogic.getParameterNode().SetParameter("Segmentation", self.segmentationNode.GetID())
        statisticsLogic.computeStatistics()
        statisticsLogic.exportToTable(tableNode, nonEmptyKeysOnly=True)
