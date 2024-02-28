from SegmentEditorLocalThresholdLib import *
from .CalculatorVolume import *


class SelectingClosedSurfaceEditorEffect(SegmentEditorEffect):
    def __init__(self, scriptedEffect):
        SegmentEditorThresholdEffect.__init__(self, scriptedEffect)
        scriptedEffect.name = "Selecting Closed Surface"
        self.applyLogic = lambda ijkPoints: self.apply(ijkPoints)

    def clone(self):
        import qSlicerSegmentationsEditorEffectsPythonQt as effects
        clonedEffect = effects.qSlicerSegmentEditorScriptedEffect(None)
        clonedEffect.setPythonSource(__file__.replace('\\', '/'))
        return clonedEffect

    def processInteractionEvents(self, callerInteractor, eventId, viewWidget):
        if eventId != vtk.vtkCommand.LeftButtonPressEvent or slicer.app.layoutManager().threeDWidget(0) == viewWidget:
            return False

        sourceImageData = self.scriptedEffect.sourceVolumeImageData()

        xy = callerInteractor.GetEventPosition()
        ijk = self.xyToIjk(xy, viewWidget, sourceImageData)

        ijkPoints = vtk.vtkPoints()
        ijkPoints.InsertNextPoint(ijk[0], ijk[1], ijk[2])
        self.applyLogic(ijkPoints)
        return True

    def setApplyLogic(self, applyLogic):
        self.applyLogic = applyLogic


class ApplierLogicWithManyMargins:
    DEFAULT_MARGIN_SIZE_IN_MM = 1.0
    DEFAULT_MINIMUM_DIAMETER_FOR_SEGMENTATION = 3.5

    def __init__(
            self,
            defaultMarginSizeInMm: float = DEFAULT_MARGIN_SIZE_IN_MM,
            minimumDiameterInMM: float = DEFAULT_MINIMUM_DIAMETER_FOR_SEGMENTATION
    ):
        self.marginSizeInMm = defaultMarginSizeInMm
        self.minimumDiameterInMm = minimumDiameterInMM

    def apply(self, calculatorVolume: CalculatorVolume, ijkPoints):
        segmentEditorWidget = calculatorVolume.segmentEditorWidget

        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SegmentationAlgorithm", "GrowCut")
        effect.setParameter("MinimumDiameterMm", self.minimumDiameterInMm)
        effect.self().apply(ijkPoints)

        segmentEditorWidget.setActiveEffectByName("Margin")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MarginSizeMm", -self.marginSizeInMm)
        effect.self().onApply()

        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod", SegmentEditorEffects.MORPHOLOGICAL_OPENING)
        effect.self().onApply()

        segmentEditorWidget.setActiveEffectByName("Islands")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", SegmentEditorEffects.REMOVE_SMALL_ISLANDS)
        effect.setParameter("MinimumSize", 3000)
        effect.self().onApply()

        segmentEditorWidget.setActiveEffectByName("Margin")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MarginSizeMm", self.marginSizeInMm)
        effect.self().onApply()


class ApplierLogicWithMask:
    DEFAULT_MINIMUM_DIAMETER = 1.0
    DEFAULT_CLOSING_SMOOTHING_SIZE = 1.5

    def __init__(self):
        self.minimumDiameter = self.DEFAULT_MINIMUM_DIAMETER
        self.closingSmoothingSize = self.DEFAULT_CLOSING_SMOOTHING_SIZE

    def apply(self, calculatorVolume: CalculatorVolume, ijkPoints):
        segmentEditorWidget = calculatorVolume.segmentEditorWidget
        volumeImageData = calculatorVolume.volumeNode.GetImageData()
        sourceVolumeMin, sourceVolumeMax = volumeImageData.GetScalarRange()

        prevSegmentID = calculatorVolume.segmentEditorNode.GetSelectedSegmentID()
        segmentation: vtkSegmentation = calculatorVolume.segmentationNode.GetSegmentation()
        maskSegmentID = segmentation.AddEmptySegment("__Mask__", "Mask")
        calculatorVolume.segmentEditorNode.SetSelectedSegmentID(maskSegmentID)

        segmentEditorWidget.setActiveEffectByName("Threshold")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MinimumThreshold", calculatorVolume.maximumThreshold + calculatorVolume.offsetThreshold)
        effect.setParameter("MaximumThreshold", sourceVolumeMax)
        effect.self().onApply()

        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod", SegmentEditorEffects.MORPHOLOGICAL_CLOSING)
        effect.setParameter("KernelSizeMm", self.closingSmoothingSize)
        effect.self().onApply()

        calculatorVolume.segmentEditorNode.SetSelectedSegmentID(prevSegmentID)
        # В идеале делать инвёрт маски черещ булеан инструмент и выбирать инсайд
        calculatorVolume.segmentEditorNode.SetMaskMode(vtkMRMLSegmentationNode.EditAllowedOutsideAllSegments)

        segmentEditorWidget.setActiveEffectByName("Selecting Closed Surface")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("MinimumThreshold", sourceVolumeMin)
        effect.setParameter("MaximumThreshold", calculatorVolume.maximumThreshold + calculatorVolume.offsetThreshold)
        effect.setParameter("SegmentationAlgorithm", "GrowCut")
        effect.setParameter("MinimumDiameterMm", self.minimumDiameter)
        effect.self().apply(ijkPoints)

        calculatorVolume.segmentEditorNode.SetMaskMode(vtkMRMLSegmentationNode.EditAllowedEverywhere)
        segmentation.RemoveSegment(maskSegmentID)

        segmentEditorWidget.setActiveEffectByName("Islands")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("Operation", SegmentEditorEffects.REMOVE_SMALL_ISLANDS)
        effect.setParameter("MinimumSize", 3000)
        effect.self().onApply()

        segmentEditorWidget.setActiveEffectByName("Smoothing")
        effect = segmentEditorWidget.activeEffect()
        effect.setParameter("SmoothingMethod", SegmentEditorEffects.MORPHOLOGICAL_CLOSING)
        effect.setParameter("KernelSizeMm", self.closingSmoothingSize)
        effect.self().onApply()
