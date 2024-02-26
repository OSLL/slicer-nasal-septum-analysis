import vtk
import slicer
from .CalculatorVolume import *


class CalculatorVolumeWidget:
    def __init__(self) -> None:
        self.ui = None
        self.logic = CalculatorVolume()
        pass

    def setup(self, uiCalculaterVolumeCategory) -> None:
        self.ui = uiCalculaterVolumeCategory

        self.ui.calculateVolume.connect('clicked(bool)', self.onCalculateVolume)

    def onCalculateVolume(self) -> None:
        """
        Run processing when user clicks "Calculate Volume" button
        """
        volumeNode = self.ui.volumeNodeForCalculateVolume.currentNode()
        segmentationNode = self.ui.segmentationNodeForCalculateVolume.currentNode()

        with slicer.util.tryWithErrorDisplay("Failed to calculate volume", waitCursor=True):
            self.logic.calculateVolume(volumeNode, segmentationNode)
