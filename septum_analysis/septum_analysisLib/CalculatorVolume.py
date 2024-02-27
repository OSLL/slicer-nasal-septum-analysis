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
    def __init__(self, marginSizeInMm: float, minimumDiameterForSegmentation: float, defaultAutothresholdMethod):
        self.isPreviewState = True
        self.segmentEditorWidget = None
        self.segmentEditorNode = None
        self.marginSizeInMm = marginSizeInMm
        self.minimumDiameterForSegmentation = minimumDiameterForSegmentation
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

    def exit(self):
        self.turnOffTool()
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
            effect.setParameter("SegmentationAlgorithm", "GrowCut")
            effect.setParameter("MinimumDiameterMm", self.minimumDiameterForSegmentation)

    def setSegmentName(self, segmentName: str):
        self.segmentName = segmentName
        self.tryChangeStateTool()

    def setVolumeNode(self, volumeNode: vtkMRMLScalarVolumeNode) -> None:
        self.volumeNode = volumeNode
        self.tryChangeStateTool()

    def setSegmentationNode(self, segmentationNode: vtkMRMLSegmentationNode) -> None:
        self.segmentationNode = segmentationNode
        self.tryChangeStateTool()

    def tryChangeStateTool(self):
        if not self.isActiveEffect():
            self.turnOffTool()
            return

        self.segmentEditorWidget.setMRMLSegmentEditorNode(self.segmentEditorNode)
        self.segmentEditorWidget.setSegmentationNode(self.segmentationNode)
        self.segmentEditorWidget.setSourceVolumeNode(self.volumeNode)
        segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()
        currentSegmentID = segmentation.GetSegmentIdBySegmentName(self.segmentName)
        if currentSegmentID == "" or currentSegmentID is None:
            currentSegmentID = segmentation.AddEmptySegment(self.segmentName, self.segmentName)
        self.segmentEditorNode.SetSelectedSegmentID(currentSegmentID)

        self.segmentEditorWidget.setActiveEffectByName("Smart Local Threshold")
        effect = self.segmentEditorWidget.activeEffect()
        effect.self().autoThreshold(self.autoThresholdMethod, SegmentEditorEffects.MODE_SET_MIN_UPPER)
        self.maximumThreshold = effect.doubleParameter("MaximumThreshold")
        effect.setParameter("MaximumThreshold", self.maximumThreshold + self.offsetThreshold)
        effect.setParameter("SegmentationAlgorithm", "GrowCut")

        def applyTool(ijkPoints):
            effect = self.segmentEditorWidget.activeEffect()
            effect.self().apply(ijkPoints)

            self.segmentEditorWidget.setActiveEffectByName("Margin")
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", -self.marginSizeInMm)
            effect.self().onApply()

            self.segmentEditorWidget.setActiveEffectByName("Smoothing")
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("SmoothingMethod", SegmentEditorEffects.MORPHOLOGICAL_OPENING)
            effect.self().onApply()

            self.segmentEditorWidget.setActiveEffectByName("Islands")
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("Operation", SegmentEditorEffects.REMOVE_SMALL_ISLANDS)
            effect.setParameter("MinimumSize", 3000)
            effect.self().onApply()

            self.segmentEditorWidget.setActiveEffectByName("Margin")
            effect = self.segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", self.marginSizeInMm)
            effect.self().onApply()

            self.segmentationNode.CreateClosedSurfaceRepresentation()
            self.tryChangeStateTool()

        effect.self().setApplyLogic(applyTool)

    def isActiveEffect(self):
        return self.isPreviewState and self.volumeNode is not None and self.segmentationNode is not None and self.segmentName is not None and self.segmentName != ""

    def turnOffTool(self):
        if self.segmentEditorWidget is None:
            return
        self.segmentEditorWidget.setActiveEffectByName(None)
        self.segmentEditorWidget.setMRMLSegmentEditorNode(None)
        self.segmentEditorWidget.setSegmentationNode(None)
        self.segmentEditorWidget.setSourceVolumeNode(None)

    def setMarginSize(self, sizeInMm: float) -> None:
        self.marginSizeInMm = sizeInMm

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
