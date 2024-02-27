import slicer
import vtk
from MRMLCorePython import vtkMRMLDisplayableNode

from .CalculatorVolume import *


class CalculatorVolumeWidget:
    DEFAULT_MARGIN_SIZE_IN_MM = 1.0
    DEFAULT_MINIMUM_DIAMETER_FOR_SEGMENTATION = 3.5

    def __init__(self) -> None:
        self.nodeAddedId = None
        self.sliceWidget = None
        self.interactor = None
        self.crosshairNode = None
        self.ui = None
        self.getterSegmentName = None
        self.logic = CalculatorVolume(
            self.DEFAULT_MARGIN_SIZE_IN_MM,
            self.DEFAULT_MINIMUM_DIAMETER_FOR_SEGMENTATION,
            SegmentEditorEffects.METHOD_TRIANGLE
        )

    def setup(self, uiCalculaterVolumeCategory) -> None:
        def registerEditorEffect():
            import os
            import qt
            import slicer.ScriptedLoadableModule

            import qSlicerSegmentationsEditorEffectsPythonQt as qSlicerSegmentationsEditorEffects
            instance = qSlicerSegmentationsEditorEffects.qSlicerSegmentEditorScriptedEffect(None)
            effectFilename = os.path.join(os.path.dirname(__file__),
                                          'SmartLocalThresholdEditorEffect.py')
            instance.setPythonSource(effectFilename.replace('\\', '/'))
            instance.self().register()

        registerEditorEffect()

        layoutManager = slicer.app.layoutManager()
        self.sliceWidget = layoutManager.sliceWidget("Red")
        sliceView = self.sliceWidget.sliceView()
        self.interactor = sliceView.interactorStyle().GetInteractor()

        self.crosshairNode = slicer.util.getNode("Crosshair")

        self.ui = uiCalculaterVolumeCategory

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
        self.ui.customNameSegmentButtonForCalculateVolume.connect(
            'clicked(bool)', lambda: self.setGetterSegmentName(CustomGetterNameSegment(self.ui))
        )

        self.ui.saveInTableButton.connect('clicked(bool)', self.onSaveInTable)
        self.enter()

    def cleanup(self):
        self.exit()

    def enter(self) -> None:
        self.nodeAddedId = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAddedOnScene)

        self.showOnlyCurrentVolume()
        self.showOnlyCurrentSegmentation()
        self.logic.enter()

    def exit(self) -> None:
        slicer.mrmlScene.RemoveObserver(self.nodeAddedId)
        self.nodeAddedId = None
        self.logic.turnOffTool()
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
        if callData.IsA("vtkMRMLScalarVolumeNode"):
            sliceViewer = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLSliceCompositeNode")
            if callData.GetID() == sliceViewer.GetBackgroundVolumeID():
                self.ui.volumeNodeForCalculateVolume.setCurrentNodeID(callData.GetID())

    # TODO: нужно у самой сегментации менять вольюм -- погуглить
    def onVolumeChanged(self):
        volumeNode = self.ui.volumeNodeForCalculateVolume.currentNode()
        self.logic.setVolumeNode(volumeNode)
        self.showOnlyCurrentVolume()
        if volumeNode is None:
            return

        segmentationNode = self.logic.segmentationNode
        if segmentationNode is None:
            return

        segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(volumeNode)

    def onSegmentationChanged(self):
        segmentationNode: vtkMRMLSegmentationNode = self.ui.segmentationNodeForCalculateVolume.currentNode()
        self.logic.setSegmentationNode(segmentationNode)
        self.showOnlyCurrentSegmentation()

        if segmentationNode is None:
            return

        segmentationNode.SetReferenceImageGeometryParameterFromVolumeNode(self.logic.volumeNode)

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
            self.logic.saveResultsToTable(tableNode)

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


class CustomGetterNameSegment:
    def __init__(self, ui) -> None:
        self.ui = ui

    def get(self) -> str:
        return self.ui.customNameSegmentForCalculateVolume.text

    def enable(self) -> None:
        self.ui.customNameSegmentForCalculateVolume.setEnabled(True)

    def disable(self) -> None:
        self.ui.customNameSegmentForCalculateVolume.setEnabled(False)
