import os
from typing import Annotated, Optional

from septum_analysisLib import *
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)

from slicer.util import pip_install


try:
    import cv2
except:
    pip_install('opencv-python')
    import cv2

try:
    import numpy as np
except:
    pip_install('numpy')
    import numpy as np

try:
    import nibabel as nib
except:
    pip_install('nibabel')
    import nibabel as nib

# from septum_detector import *

from slicer import vtkMRMLScalarVolumeNode


#
# septum_analysis
#

class septum_analysis(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "septum_analysis"
        self.parent.categories = ["septum_analysis"] 
        self.parent.dependencies = ["SegmentEditorLocalThreshold"]
        self.parent.contributors = ["Maxim Khabarov (SpbSU)", "Eugene Kalishenko (SpbSU)"]
        self.parent.helpText = """"""
        self.parent.acknowledgementText = "OSLL"

        # Additional initialization step after application startup is complete
        slicer.app.connect("startupCompleted()", registerSampleData)


#
# Register sample data sets in Sample Data module
#

def registerSampleData():
    """
    Add data sets to Sample Data module.
    """
    # It is always recommended to provide sample data for users to make it easy to try the module,
    # but if no sample data is available then this method (and associated startupCompeted signal connection) can be removed.

    import SampleData
    iconsPath = os.path.join(os.path.dirname(__file__), 'Resources/Icons')

    # To ensure that the source code repository remains small (can be downloaded and installed quickly)
    # it is recommended to store data sets that are larger than a few MB in a Github release.

    # septum_analysis1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='septum_analysis',
        sampleName='septum_analysis1',
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, 'septum_analysis1.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames='septum_analysis1.nrrd',
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums='SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95',
        # This node name will be used when the data set is loaded
        nodeNames='septum_analysis1'
    )

    # septum_analysis2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category='septum_analysis',
        sampleName='septum_analysis2',
        thumbnailFileName=os.path.join(iconsPath, 'septum_analysis2.png'),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames='septum_analysis2.nrrd',
        checksums='SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97',
        # This node name will be used when the data set is loaded
        nodeNames='septum_analysis2'
    )


#
# septum_analysisParameterNode
#

@parameterNodeWrapper
class septum_analysisParameterNode:
    """
    The parameters needed by module.

    inputVolume - The volume to threshold.
    imageThreshold - The value at which to threshold the input volume.
    invertThreshold - If true, will invert the threshold.
    thresholdedVolume - The output volume that will contain the thresholded volume.
    invertedVolume - The output volume that will contain the inverted thresholded volume.
    """
    inputVolume: vtkMRMLScalarVolumeNode
    imageThreshold: Annotated[float, WithinRange(-100, 500)] = 100
    invertThreshold: bool = False
    thresholdedVolume: vtkMRMLScalarVolumeNode
    invertedVolume: vtkMRMLScalarVolumeNode


#
# septum_analysisWidget
#

class septum_analysisWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None
        self.calculatorVolumeWidget = CalculatorVolumeWidget()

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath('UI/septum_analysis.ui'))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)
        self.calculatorVolumeWidget.setup(
            slicer.util.childWidgetVariables(self.ui.calculatorVolumeCategory)
        )

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = septum_analysisLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.applyButton.connect('clicked(bool)', self.onApplyButton)
        self.ui.downloadModelButton.connect('clicked(bool)', self.onDownloadModelButton)
        # TODO: add process for self.ui.FileButton.
        self.ui.ProcessButton.connect('clicked(bool)', self.onProcessButton)
        self.ui.FindNoseButton.connect('clicked(bool)', self.onFindNoseButton)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

    # You need to click the Reload button twice to update the submodules
    def onReload(self):
        import imp
        import septum_analysisLib as Lib
        import glob

        packageName = self.moduleName + 'Lib'
        libPath = os.path.join(os.path.dirname(__file__), Lib.__name__)
        submoduleNames = [os.path.basename(src_file)[:-3] for src_file in glob.glob(os.path.join(libPath, '*.py'))]
        f, filename, description = imp.find_module(packageName)
        package = imp.load_module(packageName, f, filename, description)
        for submoduleName in submoduleNames:
            f, filename, description = imp.find_module(submoduleName, package.__path__)
            try:
                imp.load_module(packageName + '.' + submoduleName, f, filename, description)
            finally:
                f.close()
        ScriptedLoadableModuleWidget.onReload(self)

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        self.removeObservers()
        self.calculatorVolumeWidget.cleanup()

    def enter(self) -> None:
        """
        Called each time the user opens this module.
        """
        # Make sure parameter node exists and observed
        self.initializeParameterNode()
        self.calculatorVolumeWidget.enter()

    def exit(self) -> None:
        """
        Called each time the user opens a different module.
        """
        self.calculatorVolumeWidget.exit()
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """
        Called just before the scene is closed.
        """
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """
        Called just after the scene is closed.
        """
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """
        Ensure parameter node exists and observed.
        """
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.inputVolume:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLScalarVolumeNode")
            if firstVolumeNode:
                self._parameterNode.inputVolume = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[septum_analysisParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.inputVolume and self._parameterNode.thresholdedVolume:
            self.ui.applyButton.toolTip = "Compute output volume"
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = "Select input and output volume nodes"
            self.ui.applyButton.enabled = False

    def onApplyButton(self) -> None:
        """
        Run processing when user clicks "Apply" button.
        """
        with slicer.util.tryWithErrorDisplay("Failed to compute results.", waitCursor=True):

            # Compute output
            self.logic.process(self.ui.inputSelector.currentNode(), self.ui.outputSelector.currentNode(),
                               self.ui.imageThresholdSliderWidget.value, self.ui.invertOutputCheckBox.checked)

            # Compute inverted output (if needed)
            if self.ui.invertedOutputSelector.currentNode():
                # If additional output volume is selected then result with inverted threshold is written there
                self.logic.process(self.ui.inputSelector.currentNode(), self.ui.invertedOutputSelector.currentNode(),
                                   self.ui.imageThresholdSliderWidget.value, not self.ui.invertOutputCheckBox.checked, showResult=False)

    
    '''
    Downloads models if it was not already downloaded.
    Returns true if successful.
    '''
    def downloadModels(self) -> bool:
        import requests

        MODELS_LINK = 'https://github.com/lucanchling/AMASSS_CBCT/releases/download/v1.0.2/AMASSS_Models.zip'
        FILE_NAME = 'AMASSS_Models.zip'
        FOLDER_PATH = 'AMASSS_Models'
        
        modelsPath = os.path.join(os.path.dirname(__file__), 'Resources', FILE_NAME)
        modelsFolderPath = os.path.join(os.path.dirname(__file__), 'Resources', FOLDER_PATH)

        if os.path.exists(modelsFolderPath):
            return True

        with open(modelsPath, 'wb') as modelsFile:
            response = requests.get(MODELS_LINK, allow_redirects=True, stream=True)
            total_length = int(response.headers.get('content-length'))
            progress = slicer.util.createProgressDialog(value=0, maximum=total_length)

            downloaded = 0
            for data in response.iter_content(chunk_size=1024*1024):
                downloaded += len(data)
                modelsFile.write(data)
                if progress.wasCanceled:
                    return False
                slicer.app.processEvents()
                progress.setValue(downloaded)

        import zipfile
        with zipfile.ZipFile(modelsPath, 'r') as zip_ref:
            zip_ref.extractall(modelsFolderPath)

        os.remove(modelsPath)
        return True

    def onDownloadModelButton(self) -> None:
        with slicer.util.tryWithErrorDisplay("Unable to download!", waitCursor=True):
            self.ui.downloadModelButton.enabled = not self.downloadModels()
            if not self.ui.downloadModelButton.enabled:
                self.ui.downloadModelButton.text = "Model downloaded!"
               

    def onProcessButton(self) -> None:
        inputVolume = str(self.ui.FileButton.currentPath)
        FOLDER_PATH = 'AMASSS_Models'
        modelDirectory = str(os.path.join(os.path.dirname(__file__), 'Resources', FOLDER_PATH))

        import tempfile

        outputDirecotryObject = tempfile.TemporaryDirectory()
        outputDirectory = outputDirecotryObject.name
        
        temporaryDirectoryObject = tempfile.TemporaryDirectory()
        temporatyDirectory = temporaryDirectoryObject.name

        print(temporatyDirectory)
        print(outputDirectory)

        args = {
            "inputVolume": inputVolume,
            "modelDirectory": modelDirectory,
            "highDefinition": "false",
            "skullStructure": " ".join(["MAX"]),
            "merge": "SEPARATE",
            "genVtk": "true",
            "save_in_folder": "true",
            "output_folder": outputDirectory,
            "precision": 50,
            "vtk_smooth": 1,
            "prediction_ID": "Pred",
            "gpu_usage": 5,
            "cpu_usage": 5,
            "SegmentInput": "false",
            "DCMInput": "false",
            "temp_fold": temporatyDirectory,
        }

        from SlicerAutomatedDentalTools.AMASSS_CLI import AMASSS_CLI

        cliNode2 = slicer.cli.runSync(slicer.modules.amasss_cli, None, args)
        slicer.mrmlScene.RemoveNode(cliNode2)

        outputDirecotryObject.cleanup()
        temporaryDirectoryObject.cleanup()

    def onFindNoseButton(self) -> None:
        plane1 = vtk.vtkPlaneSource()
        plane2 = vtk.vtkPlaneSource()

        min_coord = -100
        max_coord = 100

        input_volume = str(self.ui.FileButton.currentPath)

        nii_img = nib.load(input_volume)
        data = nii_img.get_fdata()
        images = []

        for i in range(data.shape[2]):
            d = data[:,:,i]
            d_min = np.min(d)
            d_max = np.max(d)
            if d_max!=d_min:
                d = (d-d_min)/(d_max-d_min)*255
            else:
                d = d*0
            images.append(d.astype(np.uint8))

        images=np.array(images)

        low, high = self.logic.find_nose(images)

        print(low, high)

        low = (low / 240) * 200 - 100
        high = (high / 240) * 200 - 100

        plane1.SetOrigin(max_coord, max_coord, low)
        plane1.SetPoint1(min_coord, max_coord, low)
        plane1.SetPoint2(max_coord, min_coord, low)

        plane2.SetOrigin(max_coord, max_coord, high)
        plane2.SetPoint1(min_coord, max_coord, high)
        plane2.SetPoint2(max_coord, min_coord, high)

        boxNode = slicer.modules.models.logic().AddModel(plane1.GetOutputPort())
        boxNode.GetDisplayNode().SetColor(1, 0, 0)
        boxNode.GetDisplayNode().SetOpacity(0.8)

        boxNode = slicer.modules.models.logic().AddModel(plane2.GetOutputPort())
        boxNode.GetDisplayNode().SetColor(0, 1, 0)
        boxNode.GetDisplayNode().SetOpacity(0.8)


#
# septum_analysisLogic
#

class septum_analysisLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self) -> None:
        """
        Called when the logic class is instantiated. Can be used for initializing member variables.
        """
        ScriptedLoadableModuleLogic.__init__(self)

    def getParameterNode(self):
        return septum_analysisParameterNode(super().getParameterNode())

    def process(self,
                inputVolume: vtkMRMLScalarVolumeNode,
                outputVolume: vtkMRMLScalarVolumeNode,
                imageThreshold: float,
                invert: bool = False,
                showResult: bool = True) -> None:
        """
        Run the processing algorithm.
        Can be used without GUI widget.
        :param inputVolume: volume to be thresholded
        :param outputVolume: thresholding result
        :param imageThreshold: values above/below this threshold will be set to 0
        :param invert: if True then values above the threshold will be set to 0, otherwise values below are set to 0
        :param showResult: show output volume in slice viewers
        """

        if not inputVolume or not outputVolume:
            raise ValueError("Input or output volume is invalid")

        import time
        startTime = time.time()
        logging.info('Processing started')

        # Compute the thresholded output volume using the "Threshold Scalar Volume" CLI module
        cliParams = {
            'InputVolume': inputVolume.GetID(),
            'OutputVolume': outputVolume.GetID(),
            'ThresholdValue': imageThreshold,
            'ThresholdType': 'Above' if invert else 'Below'
        }
        cliNode = slicer.cli.run(slicer.modules.thresholdscalarvolume, None, cliParams, wait_for_completion=True, update_display=showResult)
        # We don't need the CLI module node anymore, remove it to not clutter the scene with it
        slicer.mrmlScene.RemoveNode(cliNode)

        stopTime = time.time()
        logging.info(f'Processing completed in {stopTime-startTime:.2f} seconds')


    def find_nose(self, images: cv2.Mat):
        result, result1 = analyze_face_curvature(images)
        tr0_0 = np.quantile(result, 0.3)
        tr0_1 = np.quantile(result, 0.7)
        # tr1 = np.quantile(result1, 0.5)
        m = np.argmax(result)
        intersections1 = np.argwhere(np.diff(np.sign(result - tr0_0))).flatten()
        intersections2 = np.argwhere(np.diff(np.sign(result - tr0_1))).flatten()
        place1 = np.searchsorted(intersections1, m)
        place2 = np.searchsorted(intersections2, m)
        return intersections1[place1 - 1], intersections2[place2]


#
# septum_analysisTest
#

class septum_analysisTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear()

    def runTest(self):
        """Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_septum_analysis1()

    def test_septum_analysis1(self):
        """ Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")

        # Get/create input data

        import SampleData
        registerSampleData()
        inputVolume = SampleData.downloadSample('septum_analysis1')
        self.delayDisplay('Loaded test data set')

        inputScalarRange = inputVolume.GetImageData().GetScalarRange()
        self.assertEqual(inputScalarRange[0], 0)
        self.assertEqual(inputScalarRange[1], 695)

        outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
        threshold = 100

        # Test the module logic

        logic = septum_analysisLogic()

        # Test algorithm with non-inverted threshold
        logic.process(inputVolume, outputVolume, threshold, True)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], threshold)

        # Test algorithm with inverted threshold
        logic.process(inputVolume, outputVolume, threshold, False)
        outputScalarRange = outputVolume.GetImageData().GetScalarRange()
        self.assertEqual(outputScalarRange[0], inputScalarRange[0])
        self.assertEqual(outputScalarRange[1], inputScalarRange[1])

        self.delayDisplay('Test passed')