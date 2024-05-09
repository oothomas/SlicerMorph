import os

import qt, ctk
import slicer
import vtk

import ScreenCapture
from slicer.ScriptedLoadableModule import *


def isActorVisible(camera, actor):
    # Create a list to store the frustum planes
    frustumPlanes = [0.0] * 24

    # Get the frustum planes from the camera
    camera.GetFrustumPlanes(1.0, frustumPlanes)

    # Create a vtkPlanes object using the frustum planes
    planes = vtk.vtkPlanes()
    planes.SetFrustumPlanes(frustumPlanes)

    # Get the bounds of the actor
    bounds = actor.GetBounds()

    # Check if the bounding box is within the view frustum
    for i in range(0, 6):
        plane = vtk.vtkPlane()
        planes.GetPlane(i, plane)
        if plane.EvaluateFunction(bounds[:3]) * plane.EvaluateFunction(bounds[3:]) > 0:
            # If the product is positive, then one of the box's corners is outside this plane
            return False
    return True


#
# HiResScreenCapture
#

class HiResScreenCapture(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "HiResScreenCapture"  # TODO: make this more human readable by adding spaces
        self.parent.categories = ["SlicerMorph.Input and Output"]  # TODO: set categories (folders where the module
        # shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Murat Maga (UW), Oshane Thomas(SCRI)"]  # TODO: replace with "Firstname Lastname
        # (Organization)"
        # TODO: update with short description of the module and a link to online module documentation
        self.parent.helpText = """
The "High Resolution Screen Capture" module allows users to capture and save high-quality screenshots from the Slicer
application. Users specify the filename, output folder, and desired resolution, with the module ensuring all inputs are
 valid and the filename ends with .png. See more information in 
 <a href="https://github.com/oothomas/SlicerMorph/tree/master/HiResScreenCapture">module documentation</a>.
"""
        # TODO: replace with organization, grant and thanks
        self.parent.acknowledgementText = """This file was originally developed by Jean-Christophe Fillion-Robin, 
        Kitware Inc., Andras Lasso, PerkLab, and Steve Pieper, Isomics, Inc. and was partially funded by NIH grant 
        3P41RR013218-12S1. We would also like to thank Steve Pieper for developing the export function used here."""


#
# HiResScreenCaptureWidget
#

class HiResScreenCaptureWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.__init__(self, parent)
        self.applyButton = None
        self.threeDViewComboBox = None
        self.resolutionYSpinBox = None
        self.resolutionXSpinBox = None
        self.selectOutputDirButton = None
        self.outputDirLineEdit = None
        self.filenameLineEdit = None
        self.logic = None

    def setup(self) -> None:
        """
        Called when the user opens the module the first time and the widget is initialized.
        """
        ScriptedLoadableModuleWidget.setup(self)

        # moduleNameLabel = qt.QLabel("High Resolution Screen Capture")
        # moduleNameLabel.setAlignment(qt.Qt.AlignCenter)
        # moduleNameLabel.setStyleSheet("font-weight: bold; font-size: 18px; padding: 10px;")
        # self.layout.addWidget(moduleNameLabel)

        parametersCollapsibleButton = ctk.ctkCollapsibleButton()
        parametersCollapsibleButton.text = "Screen Capture Settings"
        self.layout.addWidget(parametersCollapsibleButton)

        parametersFormLayout = qt.QFormLayout(parametersCollapsibleButton)

        # Output filename QLineEdit
        self.filenameLineEdit = qt.QLineEdit()
        self.filenameLineEdit.setPlaceholderText("Enter filename (e.g., screenshot.png)")
        parametersFormLayout.addRow("Filename:", self.filenameLineEdit)

        # Output directory selector
        self.outputDirLineEdit = qt.QLineEdit()
        self.outputDirLineEdit.setReadOnly(True)
        self.selectOutputDirButton = qt.QPushButton("Select Output Folder")
        self.selectOutputDirButton.clicked.connect(self.selectOutputDirectory)
        directoryHBox = qt.QHBoxLayout()
        directoryHBox.addWidget(self.outputDirLineEdit)
        directoryHBox.addWidget(self.selectOutputDirButton)
        parametersFormLayout.addRow("Output Folder:", directoryHBox)

        # Resolution input fields
        self.resolutionXSpinBox = qt.QSpinBox()
        self.resolutionXSpinBox.setMinimum(1)
        self.resolutionXSpinBox.setMaximum(5000)  # You can change this max value
        self.resolutionXSpinBox.setValue(1920)  # Default value
        parametersFormLayout.addRow("X Dimension:", self.resolutionXSpinBox)

        self.resolutionYSpinBox = qt.QSpinBox()
        self.resolutionYSpinBox.setMinimum(1)
        self.resolutionYSpinBox.setMaximum(5000)  # You can change this max value
        self.resolutionYSpinBox.setValue(1080)  # Default value
        parametersFormLayout.addRow("Y Dimension:", self.resolutionYSpinBox)

        # Add a combo box for selecting the 3D view
        self.threeDViewComboBox = qt.QComboBox()
        threeDViewCount = slicer.app.layoutManager().threeDViewCount
        for i in range(threeDViewCount):
            self.threeDViewComboBox.addItem("3D View #" + str(i + 1), i)
        parametersFormLayout.addRow("3D View:", self.threeDViewComboBox)

        spacer = qt.QSpacerItem(0, 0, qt.QSizePolicy.Minimum, qt.QSizePolicy.Expanding)
        self.layout.addItem(spacer)

        # Apply button
        self.applyButton = qt.QPushButton("Export Screenshot")
        self.applyButton.clicked.connect(self.applyButtonClicked)
        self.layout.addWidget(self.applyButton)

        # Create logic class
        self.logic = HiResScreenCaptureLogic()

        # Connect signals
        self.filenameLineEdit.textChanged.connect(self.updateApplyButtonState)
        self.outputDirLineEdit.textChanged.connect(self.updateApplyButtonState)
        self.resolutionXSpinBox.valueChanged.connect(self.updateApplyButtonState)
        self.resolutionYSpinBox.valueChanged.connect(self.updateApplyButtonState)

        # Connect the update method to the layoutChanged signal
        slicer.app.layoutManager().layoutChanged.connect(self.updateThreeDViewComboBox)

        # Set initial state for the apply button
        self.updateApplyButtonState()

    def cleanup(self) -> None:
        """
        Called when the application closes and the module widget is destroyed.
        """
        slicer.app.layoutManager().layoutChanged.disconnect(self.updateThreeDViewComboBox)

    def selectOutputDirectory(self) -> None:
        """
        Open a directory selection dialog and set the output directory.
        """
        selectedDir = qt.QFileDialog.getExistingDirectory()
        if selectedDir:
            self.outputDirLineEdit.setText(selectedDir)

    def updateApplyButtonState(self) -> None:
        # Check conditions for enabling the button
        isFilenameSet = bool(self.filenameLineEdit.text.strip()) and self.filenameLineEdit.text.strip().endswith(
            '.png')
        isOutputFolderSet = bool(self.outputDirLineEdit.text.strip())
        isXResolutionSet = bool(self.resolutionXSpinBox.value)
        isYResolutionSet = bool(self.resolutionYSpinBox.value)

        # Enable or disable the button based on the conditions
        self.applyButton.setEnabled(isFilenameSet and isOutputFolderSet and isXResolutionSet and isYResolutionSet)

    def updateThreeDViewComboBox(self):
        """
        Update the items in the threeDViewComboBox with the current 3D views.
        """
        self.threeDViewComboBox.clear()
        threeDViewCount = slicer.app.layoutManager().threeDViewCount
        for i in range(threeDViewCount):
            self.threeDViewComboBox.addItem("3D View #" + str(i + 1), i)

    def applyButtonClicked(self) -> None:
        selectedThreeDWidgetIndex = self.threeDViewComboBox.currentData
        self.logic.setThreeDViewIndex(selectedThreeDWidgetIndex)

        # Set the resolution in the logic class
        self.logic.setResolution([self.resolutionXSpinBox.value, self.resolutionYSpinBox.value])

        outputPath = os.path.join(self.outputDirLineEdit.text, self.filenameLineEdit.text)
        self.logic.setOutputPath(outputPath)
        self.logic.runScreenCapture()


#
# HiResScreenCaptureLogic
#

class HiResScreenCaptureLogic(ScriptedLoadableModuleLogic):
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

        self.threeDViewIndex = 0
        self.resolution = None
        self.outputPath = None

    def setResolution(self, resolution: list) -> None:

        self.resolution = resolution

    def setOutputPath(self, outputPath: str) -> None:
        self.outputPath = outputPath

    def setThreeDViewIndex(self, index: int) -> None:
        self.threeDViewIndex = index

    def runScreenCapture(self) -> None:
        if self.resolution and self.outputPath:
            layoutManager = slicer.app.layoutManager()
            originalLayout = layoutManager.layout
            originalViewNode = layoutManager.threeDWidget(self.threeDViewIndex).mrmlViewNode()
            originalCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(originalViewNode)

            # Debugging: Print original camera settings
            print("Original Camera Settings:")
            print("Position:", originalCamera.GetPosition())
            print("Focal Point:", originalCamera.GetFocalPoint())
            print("View Up:", originalCamera.GetViewUp())

            layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDualMonitorFourUpView)
            viewNode = layoutManager.threeDWidget(self.threeDViewIndex).mrmlViewNode()
            layoutManager.addMaximizedViewNode(viewNode)
            newCamera = slicer.modules.cameras.logic().GetViewActiveCameraNode(viewNode)

            # Set and debug new camera settings
            newCamera.SetPosition(originalCamera.GetPosition())
            newCamera.SetFocalPoint(originalCamera.GetFocalPoint())
            newCamera.SetViewUp(originalCamera.GetViewUp())
            print("New Camera Settings Applied")

            # Resize and capture the view
            # viewWidget = layoutManager.threeDWidget(0)
            viewWidget = layoutManager.viewWidget(viewNode)
            layoutDockingWidget = viewWidget.parent().parent()
            originalSize = layoutDockingWidget.size
            layoutDockingWidget.resize(self.resolution[0], self.resolution[1])

            # Force a redraw
            layoutManager.threeDWidget(0).threeDView().scheduleRender()

            # Capture the view
            cap = ScreenCapture.ScreenCaptureLogic()
            cap.captureImageFromView(viewWidget.threeDView(), self.outputPath)

            # Restore original size and layout
            layoutDockingWidget.resize(originalSize.width(), originalSize.height())
            layoutManager.setLayout(originalLayout)

            print("Capture Completed")

    # def runScreenCapture(self) -> None:
    #     if self.resolution and self.outputPath:
    #         # Switch to a layout that has a window that is not in the main window
    #         layoutManager = slicer.app.layoutManager()
    #         originalLayout = layoutManager.layout
    #         layoutManager.setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutDualMonitorFourUpView)
    #
    #         # Maximize the 3D view within this layout
    #         viewLogic = slicer.app.applicationLogic().GetViewLogicByLayoutName("1+")
    #         viewNode = viewLogic.GetViewNode()
    #         layoutManager.addMaximizedViewNode(viewNode)
    #
    #         # Resize the view
    #         viewWidget = layoutManager.viewWidget(viewNode)
    #         # Parent of the view widget is the frame, parent of the frame is the docking widget
    #         layoutDockingWidget = viewWidget.parent().parent()
    #         originalSize = layoutDockingWidget.size
    #         layoutDockingWidget.resize(self.resolution[0], self.resolution[1])
    #
    #         # Capture the view
    #         cap = ScreenCapture.ScreenCaptureLogic()
    #         cap.captureImageFromView(viewWidget.threeDView(), self.outputPath)
    #         # Restore original size and layout
    #         layoutDockingWidget.resize(originalSize)
    #         layoutManager.setLayout(originalLayout)

    # def runScreenCapture(self) -> None:
    #     if self.resolution and self.outputPath:
    #         vtk.vtkGraphicsFactory()
    #         gf = vtk.vtkGraphicsFactory()
    #         gf.SetOffScreenOnlyMode(1)
    #         gf.SetUseMesaClasses(1)
    #         rw = vtk.vtkRenderWindow()
    #         rw.SetOffScreenRendering(1)
    #         ren = vtk.vtkRenderer()
    #         rw.SetSize(self.resolution[0], self.resolution[1])
    #
    #         lm = slicer.app.layoutManager()
    #
    #         threeDViewWidget = lm.threeDWidget(self.threeDViewIndex)
    #         threeDView = threeDViewWidget.threeDView()
    #
    #         renderers = threeDView.renderWindow().GetRenderers()
    #         ren3d = renderers.GetFirstRenderer()
    #
    #         # Set the background color of the off-screen renderer to match the original
    #         backgroundColor = ren3d.GetBackground()
    #         ren.SetBackground(backgroundColor)
    #
    #         camera = ren3d.GetActiveCamera()
    #
    #         while ren3d:
    #
    #             actors = ren3d.GetActors()
    #             for index in range(actors.GetNumberOfItems()):
    #                 actor = actors.GetItemAsObject(index)
    #
    #                 actor_class_name = actor.GetClassName()  # Get the class name using VTK's method
    #                 # Alternatively, use Python's type function: actor_type = type(actor).__name__
    #                 print("Actor index:", index, "Class name:", actor_class_name)
    #
    #                 property = actor.GetProperty()
    #                 # print("Actor Property:", property)
    #                 representation = property.GetRepresentation()
    #
    #                 # vtkProperty defines three representation types:
    #                 # vtkProperty.VTK_POINTS, vtkProperty.VTK_WIREFRAME, vtkProperty.VTK_SURFACE
    #                 if representation == vtk.VTK_POINTS:
    #                     print("Actor index:", index, "is represented as points.")
    #                 elif representation == vtk.VTK_WIREFRAME:
    #                     print("Actor index:", index, "is represented as wireframe.")
    #                 elif representation == vtk.VTK_SURFACE:
    #                     print("Actor index:", index, "is represented as a surface.")
    #                 else:
    #                     print("Actor index:", index, "has an unknown representation.")
    #
    #                 print("Actor index:", index, "Visibility -", actor.GetVisibility(), "|", isActorVisible(camera, actor))
    #                 if actor.GetVisibility():  # and isActorVisible(camera, actor):
    #                     ren.AddActor(actor)  # Add only visible actors
    #
    #             lights = ren3d.GetLights()
    #             for index in range(lights.GetNumberOfItems()):
    #                 ren.AddLight(lights.GetItemAsObject(index))
    #
    #             volumes = ren3d.GetVolumes()
    #             for index in range(volumes.GetNumberOfItems()):
    #                 ren.AddVolume(volumes.GetItemAsObject(index))
    #
    #             ren3d = renderers.GetNextItem()
    #
    #         ren.SetActiveCamera(camera)
    #
    #         rw.AddRenderer(ren)
    #         rw.Render()
    #
    #         wti = vtk.vtkWindowToImageFilter()
    #         wti.SetInput(rw)
    #         wti.Update()
    #         writer = vtk.vtkPNGWriter()
    #         writer.SetInputConnection(wti.GetOutputPort())
    #         writer.SetFileName(self.outputPath)
    #         writer.Update()
    #         writer.Write()
    #         i = wti.GetOutput()

        #
# HiResScreenCaptureTest
#

# class HiResScreenCaptureTest(ScriptedLoadableModuleTest):
#     """
#     This is the test case for your scripted module.
#     Uses ScriptedLoadableModuleTest base class, available at:
#     https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
#     """
#
#     def setUp(self):
#         """ Do whatever is needed to reset the state - typically a scene clear will be enough.
#         """
#         slicer.mrmlScene.Clear()
#
#     def runTest(self):
#         """Run as few or as many tests as needed here.
#         """
#         self.setUp()
#         self.test_HiResScreenCapture1()
#
#     def test_HiResScreenCapture1(self):
#         """ Ideally you should have several levels of tests.  At the lowest level
#         tests should exercise the functionality of the logic with different inputs
#         (both valid and invalid).  At higher levels your tests should emulate the
#         way the user would interact with your code and confirm that it still works
#         the way you intended.
#         One of the most important features of the tests is that it should alert other
#         developers when their changes will have an impact on the behavior of your
#         module.  For example, if a developer removes a feature that you depend on,
#         your test should break so they know that the feature is needed.
#         """
#
#         self.delayDisplay("Starting the test")
#
#         # Get/create input data
#
#         import SampleData
#         registerSampleData()
#         inputVolume = SampleData.downloadSample('HiResScreenCapture1')
#         self.delayDisplay('Loaded test data set')
#
#         inputScalarRange = inputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(inputScalarRange[0], 0)
#         self.assertEqual(inputScalarRange[1], 695)
#
#         outputVolume = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode")
#         threshold = 100
#
#         # Test the module logic
#
#         logic = HiResScreenCaptureLogic()
#
#         # Test algorithm with non-inverted threshold
#         logic.process(inputVolume, outputVolume, threshold, True)
#         outputScalarRange = outputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(outputScalarRange[0], inputScalarRange[0])
#         self.assertEqual(outputScalarRange[1], threshold)
#
#         # Test algorithm with inverted threshold
#         logic.process(inputVolume, outputVolume, threshold, False)
#         outputScalarRange = outputVolume.GetImageData().GetScalarRange()
#         self.assertEqual(outputScalarRange[0], inputScalarRange[0])
#         self.assertEqual(outputScalarRange[1], inputScalarRange[1])
#
#         self.delayDisplay('Test passed')
