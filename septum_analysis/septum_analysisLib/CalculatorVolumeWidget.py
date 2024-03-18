import slicer
import vtk
import qt
from MRMLCorePython import vtkMRMLDisplayableNode

from .CalculatorVolume import *
from .SelectingClosedSurfaceEditorEffect import *
from .utils import registerEditorEffect
from .PipelineApplierLogic import UpdaterActionsOnProgressBar


class CalculatorVolumeWidget:
    def __init__(self) -> None:
        self.isEntered = False
        self.logic = None
        self.nodeAddedId = None
        self.crosshairNode = None
        self.ui = None
        self.getterSegmentName = None

    def setup(self, uiCalculaterVolumeCategory) -> None:
        registerEditorEffect(__file__, 'SelectingClosedSurfaceEditorEffect.py')

        self.crosshairNode = slicer.util.getNode("Crosshair")

        self.ui = uiCalculaterVolumeCategory
        self.ui.progressBarForCalculatorVolume.hide()

        applierLogic = ApplierLogicWithMask(UpdaterActionsOnProgressBar(self.ui))
        self.logic = CalculatorVolume(
            applierLogic,
            SegmentEditorEffects.METHOD_TRIANGLE,
            self.ui.isPreviewCheckBox.checked
        )

        self.ui.volumeNodeForCalculateVolume.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onVolumeChanged
        )
        self.ui.segmentationNodeForCalculateVolume.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSegmentationChanged
        )

        self.ui.thresholdOffset.connect("valueChanged(double)", lambda value: self.logic.setOffsetThreshold(value))
        self.ui.isPreviewCheckBox.connect("clicked(bool)", lambda value: self.logic.setIsPreviewState(value))

        self.ui.autothresholdMethod.addItem("Triangle", SegmentEditorEffects.METHOD_TRIANGLE)
        self.ui.autothresholdMethod.addItem("Kittler Illingworth", SegmentEditorEffects.METHOD_KITTLER_ILLINGWORTH)
        self.ui.autothresholdMethod.addItem("Otsu", SegmentEditorEffects.METHOD_OTSU)
        self.ui.autothresholdMethod.connect("currentIndexChanged(int)", self.onAutoThresholdChanged)

        self.ui.leftSinusButton.setChecked(True)
        self.setGetterSegmentName(ConstGetterNameSegment(self.ui.leftSinusButton.text))

        self.ui.leftSinusButton.connect(
            'clicked(bool)', lambda: self.setGetterSegmentName(ConstGetterNameSegment(self.ui.leftSinusButton.text))
        )
        self.ui.rightSinusButton.connect(
            'clicked(bool)', lambda: self.setGetterSegmentName(ConstGetterNameSegment(self.ui.rightSinusButton.text))
        )

        self.ui.saveInTableButton.connect('clicked(bool)', self.onSaveInTable)

        self.enter()

    def cleanup(self):
        self.exit()

    def enter(self) -> None:
        if self.isEntered:
            return
        self.isEntered = True

        self.nodeAddedId = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAddedOnScene)

        self.showOnlyCurrentVolume()
        self.showOnlyCurrentSegmentation()
        self.logic.enter()

    def exit(self) -> None:
        self.isEntered = False
        slicer.mrmlScene.RemoveObserver(self.nodeAddedId)
        self.nodeAddedId = None
        self.logic.exit()

    def setGetterSegmentName(self, getterSegmentName):
        if self.getterSegmentName is not None:
            self.getterSegmentName.disable()
        self.getterSegmentName = getterSegmentName
        if self.getterSegmentName is not None:
            self.getterSegmentName.enable()

        self.logic.setSegmentName(getterSegmentName.get())

    def onAutoThresholdChanged(self, changedIndex: int):
        autoThresholdMethod = self.ui.autothresholdMethod.itemData(changedIndex)
        self.logic.setAutoThresholdMethod(autoThresholdMethod)

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def onNodeAddedOnScene(self, caller, eventId, callData):
        if not callData.IsA("vtkMRMLScalarVolumeNode"):
            return

        # I would like to change only when the background change from there,
        # but slicer.mrmlScene.GetNthNodeByClass(i, "vtkMRMLSliceCompositeNode").GetBackgroundVolumeID()
        # still hasn't changed in this event.
        self.ui.volumeNodeForCalculateVolume.setCurrentNodeID(callData.GetID())

    def onVolumeChanged(self):
        volumeNode = self.ui.volumeNodeForCalculateVolume.currentNode()
        if self.logic.volumeNode != volumeNode:
            self.logic.setVolumeNode(volumeNode)
        self.showOnlyCurrentVolume()

    def onSegmentationChanged(self):
        segmentationNode: vtkMRMLSegmentationNode = self.ui.segmentationNodeForCalculateVolume.currentNode()

        self.logic.setSegmentationNode(segmentationNode)
        self.showOnlyCurrentSegmentation()
        self.ui.segmentationShow3DButton.setSegmentationNode(segmentationNode)
        self.ui.volumeNodeForCalculateVolume.setCurrentNodeID(
            None if self.logic.volumeNode is None else self.logic.volumeNode.GetID()
        )

    def showOnlyCurrentVolume(self):
        volumeNode = self.logic.volumeNode
        slicer.util.setSliceViewerLayers(background=volumeNode)

        self.resetFovOnAllSlices()

    @staticmethod
    def resetFovOnAllSlices():
        sliceWidgetNames = slicer.app.layoutManager().sliceViewNames()
        for sliceWidgetName in sliceWidgetNames:
            sliceWidget = slicer.app.layoutManager().sliceWidget(sliceWidgetName)

            # Reset the FieldOfView
            sliceWidget.sliceLogic().FitSliceToAll()
            # Update the slice view
            sliceWidget.sliceController().fitSliceToBackground()

    def showOnlyCurrentSegmentation(self):
        self.showOnlyTargetNode('vtkMRMLSegmentationNode', self.logic.segmentationNode)

    @staticmethod
    def showOnlyTargetNode(typeNode: str, targetNode: vtkMRMLDisplayableNode):
        nodes = slicer.util.getNodesByClass(typeNode)
        for itNode in nodes:
            itNode.SetDisplayVisibility(1 if itNode == targetNode else 0)

    def onSaveInTable(self):
        tableNode: vtkMRMLTableNode = self.ui.tableNodeForCalculateVolume.currentNode()

        with slicer.util.tryWithErrorDisplay("Failed to save results", waitCursor=True):
            isNeedSwitch3D = not self.ui.segmentationShow3DButton.checked
            if isNeedSwitch3D:
                self.ui.segmentationShow3DButton.clicked(True)

            self.logic.saveResultsToTable(tableNode)

            if isNeedSwitch3D:
                self.ui.segmentationShow3DButton.clicked(False)

            slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutFourUpTableView)
            slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(tableNode.GetID())
            slicer.app.applicationLogic().PropagateTableSelection()


class ConstGetterNameSegment:
    def __init__(self, segmentName: str) -> None:
        self.segmentName = segmentName

    def get(self) -> str:
        return self.segmentName

    def enable(self) -> None:
        pass

    def disable(self) -> None:
        pass
