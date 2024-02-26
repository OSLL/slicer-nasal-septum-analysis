import logging

import vtk
import slicer

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
    MARGIN_SIZE_IN_MM = 1.5

    def calculateVolume(self, volumeNode: vtkMRMLScalarVolumeNode, segmentationNode: vtkSegmentation) -> None:
        if volumeNode is None or segmentationNode is None:
            return

        # Работа с эффектами взята отсюда
        # https://gist.github.com/lassoan/1673b25d8e7913cbc245b4f09ed853f9

        thresholdRange = volumeNode.GetImageData().GetScalarRange()
        originVector = volumeNode.GetOrigin()

        segmentationNode.CreateDefaultDisplayNodes()  # only needed for display
        segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

        segmentation: vtkSegmentation = segmentationNode.GetSegmentation()
        addedSegmentID = segmentation.AddEmptySegment("Overall")

        segmentEditorWidget: Optional[SegmentEditorWidget] = slicer.qMRMLSegmentEditorWidget()
        segmentEditorWidget.setMRMLScene(slicer.mrmlScene)
        segmentEditorNode: Optional[vtkMRMLSegmentEditorNode] = None
        try:
            segmentEditorNode: vtkMRMLSegmentEditorNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentEditorNode")
            segmentEditorWidget.setMRMLSegmentEditorNode(segmentEditorNode)
            segmentEditorWidget.setSegmentationNode(segmentationNode)
            segmentEditorWidget.setMasterVolumeNode(volumeNode)

            segmentEditorWidget.setActiveEffectByName("Threshold")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MinimumThreshold", thresholdRange[0])
            effect.self().autoThreshold(SegmentEditorEffects.METHOD_KITTLER_ILLINGWORTH,
                                        SegmentEditorEffects.MODE_SET_MIN_UPPER)
            effect.self().onApply()

            segmentEditorWidget.setActiveEffectByName("Margin")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", -self.MARGIN_SIZE_IN_MM)
            effect.self().onApply()

            segmentEditorWidget.setActiveEffectByName("Islands")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("Operation", SegmentEditorEffects.SPLIT_ISLANDS_TO_SEGMENTS)
            effect.setParameter("MinimumSize", 70000)
            effect.self().onApply()

            # TODO: там на самом деле может остаться не три сегмента и самым первым может оказаться не лишний
            segmentation.RemoveSegment(addedSegmentID)

            leftSegment: vtkSegment = segmentation.GetNthSegment(0)
            leftSegment.SetNameAutoGenerated(False)
            leftSegment.SetName("Left")

            rightSegment: vtkSegment = segmentation.GetNthSegment(1)
            rightSegment.SetNameAutoGenerated(False)
            rightSegment.SetName("Right")

            segmentEditorNode.SetSelectedSegmentID(segmentation.GetNthSegmentID(0))

            segmentEditorWidget.setActiveEffectByName("Margin")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", self.MARGIN_SIZE_IN_MM)
            effect.self().onApply()

            segmentEditorNode.SetSelectedSegmentID(segmentation.GetNthSegmentID(1))

            segmentEditorWidget.setActiveEffectByName("Margin")
            effect = segmentEditorWidget.activeEffect()
            effect.setParameter("MarginSizeMm", self.MARGIN_SIZE_IN_MM)
            effect.self().onApply()

            segmentEditorWidget = None

        finally:
            slicer.mrmlScene.RemoveNode(segmentEditorNode)

        segmentationNode.CreateClosedSurfaceRepresentation()

        tableNode: vtkMRMLTableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", "Volume statistics")

        statisticsLogic: SegmentStatisticsLogic = SegmentStatistics.SegmentStatisticsLogic()
        statisticsLogic.getParameterNode().SetParameter("Segmentation", segmentationNode.GetID())
        statisticsLogic.computeStatistics()
        statisticsLogic.computeStatistics()
        statisticsLogic.exportToTable(tableNode, nonEmptyKeysOnly=True)

        tableWidget = slicer.app.layoutManager().tableWidget(0)
        tableWidget.tableView().setMRMLTableNode(tableNode)