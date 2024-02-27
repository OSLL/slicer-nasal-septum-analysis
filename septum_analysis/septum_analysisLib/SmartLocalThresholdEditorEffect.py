from SegmentEditorLocalThresholdLib import *


class SmartLocalThresholdEditorEffect(SegmentEditorEffect):
    def __init__(self, scriptedEffect):
        SegmentEditorThresholdEffect.__init__(self, scriptedEffect)
        scriptedEffect.name = "Smart Local Threshold"
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
