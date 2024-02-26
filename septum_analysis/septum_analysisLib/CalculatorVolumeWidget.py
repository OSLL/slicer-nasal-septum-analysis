import vtk
import slicer
from .CalculatorVolume import *
from MRMLCorePython import vtkMRMLDisplayableNode


class CalculatorVolumeWidget:
    DEFAULT_MARGIN_SIZE_IN_MM = 1.6

    def __init__(self) -> None:
        self.nodeAddedId = None
        self.leftButtonPressedId = None
        self.sliceWidget = None
        self.interactor = None
        self.crosshairNode = None
        self.ui = None
        self.getterSegmentName = None
        self.logic = CalculatorVolume(self.DEFAULT_MARGIN_SIZE_IN_MM)

    def setup(self, uiCalculaterVolumeCategory) -> None:
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

        self.ui.autothrsholdMethod.addItem("Huang", SegmentEditorEffects.METHOD_HUANG)
        self.ui.autothrsholdMethod.addItem("IsoData", SegmentEditorEffects.METHOD_ISO_DATA)

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

    def cleanup(self):
        self.exit()

    def enter(self) -> None:
        self.leftButtonPressedId = self.interactor.AddObserver(
            vtk.vtkCommand.LeftButtonReleaseEvent, self.onLeftButtonPressed
        )
        self.nodeAddedId = slicer.mrmlScene.AddObserver(slicer.vtkMRMLScene.NodeAddedEvent, self.onNodeAddedOnScene)

        self.showOnlyCurrentVolume()
        self.showOnlyCurrentSegmentation()

    def exit(self) -> None:
        self.interactor.RemoveObserver(self.leftButtonPressedId)
        slicer.mrmlScene.RemoveObserver(self.nodeAddedId)
        self.leftButtonPressedId = None
        self.nodeAddedId = None

    def setGetterSegmentName(self, getterSegmentName):
        if self.getterSegmentName is not None:
            self.getterSegmentName.disable()
        self.getterSegmentName = getterSegmentName
        if self.getterSegmentName is not None:
            self.getterSegmentName.enable()

    @vtk.calldata_type(vtk.VTK_OBJECT)
    def onNodeAddedOnScene(self, caller, eventId, callData):
        if callData.IsA("vtkMRMLScalarVolumeNode"):
            sliceViewer = slicer.mrmlScene.GetNthNodeByClass(0, "vtkMRMLSliceCompositeNode")
            if callData.GetID() == sliceViewer.GetBackgroundVolumeID():
                self.ui.volumeNodeForCalculateVolume.setCurrentNodeID(callData.GetID())

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

    def onLeftButtonPressed(self, observer, eventId):
        position = [0, 0, 0]
        self.crosshairNode.GetCursorPositionXYZ(position)

        with slicer.util.tryWithErrorDisplay("Failed to calculate volume", waitCursor=True):
            methodIndex = self.ui.autothrsholdMethod.currentIndex
            autoThresholdMethod = self.ui.autothrsholdMethod.itemData(methodIndex)

            self.logic.calculateVolume(
                self.getterSegmentName.get(), autoThresholdMethod, position, self.sliceWidget
            )
            self.logic.segmentationNode.CreateClosedSurfaceRepresentation()

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
