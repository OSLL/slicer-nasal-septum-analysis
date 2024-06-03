from .SinusesManipulator import *
from .PipelineApplierLogic import *


def getLibModule():
    from pathlib import Path
    import imp
    import sys
    pathToSegmentEffect = Path(sys.modules['SegmentEditorLocalThreshold'].__file__)
    pathToSegmentEffect = pathToSegmentEffect.parent.joinpath("SegmentEditorLocalThresholdLib/SegmentEditorEffect.py")
    return imp.load_source(
        'SegmentEditorLocalThresholdLib.SegmentEditorEffect',
        pathToSegmentEffect.__str__()
    )


LocalThresholdLib = getLibModule()


# Unfortunately, there is no unregistration function, so this effect can be seen in SegmentEditor
class SelectingClosedSurfaceEditorEffect(LocalThresholdLib.SegmentEditorEffect):
    def __init__(self, scriptedEffect):
        LocalThresholdLib.SegmentEditorEffect.__init__(self, scriptedEffect)
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


class ApplierLogicWithMask:
    DEFAULT_MINIMUM_DIAMETER = 3.5
    DEFAULT_CLOSING_SMOOTHING_SIZE = 1.0
    DEFAULT_CLOSING_SMOOTHING_SIZE_FOR_END = 1.0

    class Data:
        def __init__(self, calculatorVolume: CalculatorVolume, ijkPoints):
            self.prevSegmentID = None
            self.maskSegmentID = None
            self.segmentation: Optional[vtkSegmentation] = None

            self.calculatorVolume = calculatorVolume
            self.ijkPoints = ijkPoints
            self.segmentEditorWidget = calculatorVolume.segmentEditorWidget
            self.volumeImageData = calculatorVolume.volumeNode.GetImageData()
            self.sourceVolumeMin, self.sourceVolumeMax = self.volumeImageData.GetScalarRange()
            self.threshold = calculatorVolume.maximumThreshold + calculatorVolume.offsetThreshold

    def __init__(self, updaterActions):
        self.minimumDiameter = self.DEFAULT_MINIMUM_DIAMETER
        self.closingSmoothingSize = self.DEFAULT_CLOSING_SMOOTHING_SIZE
        self.closingSmoothingSizeForEnd = self.DEFAULT_CLOSING_SMOOTHING_SIZE_FOR_END
        self.pipeline = PipelineApplierLogic(
            updaterActions,
            lambda calculatorVolume, ijkPoints: ApplierLogicWithMask.Data(calculatorVolume, ijkPoints)
        )

        def createAndSetMaskSegment(data: ApplierLogicWithMask.Data):
            data.prevSegmentID = data.calculatorVolume.segmentEditorNode.GetSelectedSegmentID()
            data.segmentation = data.calculatorVolume.segmentationNode.GetSegmentation()
            data.maskSegmentID = data.segmentation.AddEmptySegment("__Mask__", "Mask")
            data.calculatorVolume.segmentEditorNode.SetSelectedSegmentID(data.maskSegmentID)

        self.pipeline.addAction(createAndSetMaskSegment)
        self.pipeline.addAction(EditorEffectAction('Threshold', {
            'MinimumThreshold': lambda data: data.threshold,
            'MaximumThreshold': lambda data: data.sourceVolumeMax,
        }))
        self.pipeline.addAction(EditorEffectAction('Logical operators', {
            'Operation': lambda _: SegmentEditorEffects.LOGICAL_INVERT,
        }))

        def changeCurrentNodeAndMaskNode(data: ApplierLogicWithMask.Data):
            data.calculatorVolume.segmentEditorNode.SetSelectedSegmentID(data.prevSegmentID)
            data.calculatorVolume.segmentEditorNode.SetMaskSegmentID(data.maskSegmentID)
            data.calculatorVolume.segmentEditorNode.SetMaskMode(vtkMRMLSegmentationNode.EditAllowedInsideSingleSegment)

        self.pipeline.addAction(changeCurrentNodeAndMaskNode)
        # self.pipeline.addAction(EditorEffectAction('Smoothing', {
        #     'SmoothingMethod': lambda _: SegmentEditorEffects.MORPHOLOGICAL_CLOSING,
        #     'KernelSizeMm': lambda _: self.closingSmoothingSize,
        # }))
        self.pipeline.addAction(EditorEffectAction('Selecting Closed Surface', {
            'MinimumThreshold': lambda data: data.sourceVolumeMin,
            'MaximumThreshold': lambda data: data.threshold,
            'MinimumDiameterMm': lambda _: self.minimumDiameter,
            # 'SegmentationAlgorithm': lambda _: 'GrowCut',
            # TODO: ругается на то, что как-будто нет ImageData, хотя при GrowCut никогда не ругается
            'SegmentationAlgorithm': lambda _: 'WaterShed',
            'FeatureSizeMm': lambda _: 0.1,
        }, lambda data, effect: effect.self().apply(data.ijkPoints)))

        def returnMaskNodeAndRemoveMaskSegments(data: ApplierLogicWithMask.Data):
            data.calculatorVolume.segmentEditorNode.SetMaskMode(vtkMRMLSegmentationNode.EditAllowedEverywhere)
            data.calculatorVolume.segmentEditorNode.SetMaskSegmentID(None)
            data.segmentation.RemoveSegment(data.maskSegmentID)

        self.pipeline.addAction(returnMaskNodeAndRemoveMaskSegments)
        self.pipeline.addAction(EditorEffectAction('Islands', {
            'Operation': lambda _: SegmentEditorEffects.REMOVE_SMALL_ISLANDS,
            'MinimumSize': lambda _: 1000,
        }))
        self.pipeline.addAction(EditorEffectAction('Smoothing', {
            'SmoothingMethod': lambda _: SegmentEditorEffects.MORPHOLOGICAL_CLOSING,
            'KernelSizeMm': lambda _: self.closingSmoothingSizeForEnd,
        }))

    def apply(self, calculatorVolume: CalculatorVolume, ijkPoints):
        self.pipeline.run(calculatorVolume, ijkPoints)
