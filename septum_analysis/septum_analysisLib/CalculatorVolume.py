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
    SegmentEditorThresholdEffect,
    SegmentEditorMarginEffect,
    SegmentEditorIslandsEffect
)
import SegmentEditorEffects


class CalculatorVolume:
    def __init__(self, marginSizeInMm: float):
        self.marginSizeInMm = marginSizeInMm
        self.volumeNode = None
        self.segmentationNode = None

    def setVolumeNode(self, volumeNode: vtkMRMLScalarVolumeNode) -> None:
        self.volumeNode = volumeNode

    def setSegmentationNode(self, segmentationNode: vtkMRMLSegmentationNode) -> None:
        self.segmentationNode = segmentationNode

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


    def calculateVolume(
            self,
            segmentName: str,
            autoThresholdMethod,
            cursorPosition: List[int],
            sliceWidget
    ) -> None:
        if self.volumeNode is None:
            raise ValueError("Volume node not selected")
        if self.segmentationNode is None:
            raise ValueError("Segmentation node not selected")
        if segmentName is None:
            raise ValueError("Segment name is none")

        if len(cursorPosition) != 3:
            raise ValueError("List should have exactly 3 elements")

        # Работа с эффектами взята отсюда
        # https://gist.github.com/lassoan/1673b25d8e7913cbc245b4f09ed853f9
        segmentation: vtkSegmentation = self.segmentationNode.GetSegmentation()

        segmentEditorWidget: Optional[SegmentEditorWidget] = slicer.qMRMLSegmentEditorWidget()
        segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        segmentEditorNode: vtkMRMLSegmentEditorNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLSegmentEditorNode"
        )
        try:
            segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
            segmentEditorWidget.setSegmentationNode(self.segmentationNode)
            segmentEditorWidget.setMasterVolumeNode(self.volumeNode)

            currentSegmentID = segmentation.GetSegmentIdBySegmentName(segmentName)
            if currentSegmentID == "" or currentSegmentID is None:
                currentSegmentID = segmentation.AddEmptySegment(segmentName, segmentName)

            segmentEditorNode.SetSelectedSegmentID(currentSegmentID)

            segmentEditorWidget.setActiveEffectByName("Local Threshold")
            effect = segmentEditorWidget.activeEffect()
            effect.self().autoThreshold(autoThresholdMethod, SegmentEditorEffects.MODE_SET_MIN_UPPER)
            effect.setParameter("SegmentationAlgorithm", "GrowCut")

            sourceImageData = effect.self().scriptedEffect.sourceVolumeImageData()
            ijk = effect.self().xyToIjk([cursorPosition[0], cursorPosition[1]], sliceWidget, sourceImageData)

            ijkPoints = vtk.vtkPoints()
            ijkPoints.InsertNextPoint(ijk[0], ijk[1], ijk[2])
            effect.self().scriptedEffect.parameterSetNode()
            effect.self().apply(ijkPoints)

            segmentEditorWidget.setActiveEffectByName("Margin")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", -self.marginSizeInMm)
            effect.self().onApply()

            segmentEditorWidget.setActiveEffectByName("Islands")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("Operation", SegmentEditorEffects.REMOVE_SMALL_ISLANDS)
            effect.setParameter("MinimumSize", 1000)
            effect.self().onApply()

            segmentEditorWidget.setActiveEffectByName("Margin")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", self.marginSizeInMm)
            effect.self().onApply()

            segmentEditorWidget.setActiveEffectByName(None)
        finally:
            slicer.mrmlScene.RemoveNode(segmentEditorNode)
