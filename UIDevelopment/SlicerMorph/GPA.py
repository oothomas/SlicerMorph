import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import math


import re
import csv
import glob
import fnmatch

import support.vtk_lib as vtk_lib
import support.gpa_lib as gpa_lib
import  numpy as np
from datetime import datetime

#
# GPA
#


class GPA(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "GPA" # TODO make this more human readable by adding spaces
    self.parent.categories = ["SlicerMorph"]
    self.parent.dependencies = []
    self.parent.contributors = [" Sara Rolfe (UW), Murat Maga (UW)"] # replace with "Firstname Lastname (Organization)"
    self.parent.helpText = """
This module preforms standard Generalized Procrustes Analysis (GPA) based on (citation)
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This module was developed by Sara Rolfe and Murat Maga, through a NSF ABI Development grant, "An Integrated Platform for Retrieval, Visualization and Analysis of 
3D Morphology From Digital Biological Collections" (Award Numbers: 1759883 (Murat Maga), 1759637 (Adam Summers), 1759839 (Douglas Boyer)).
https://nsf.gov/awardsearch/showAward?AWD_ID=1759883&HistoricalAwards=false 
""" # replace with organization, grant and thanks.

#
# GPAWidget
#
class sliderGroup(qt.QGroupBox):
  def setValue(self, value):
        self.slider.setValue(value)

  def connectList(self,mylist):
    self.list=mylist

  def populateComboBox(self, boxlist):
    self.comboBox.clear()
    for i in boxlist:
        self.comboBox.addItem(i)

  def setLabelTest(self,i):
    j=str(i)
    self.label.setText(j)

  def boxValue(self):
    tmp=self.comboBox.currentIndex
    return tmp

  def sliderValue(self):
    tmp=self.spinBox.value
    return tmp

  def clear(self):
    self.spinBox.setValue(0)
    self.comboBox.clear()
    
  def __init__(self, parent=None):
    super(sliderGroup, self).__init__( parent)

    # slider
    self.slider = qt.QSlider(qt.Qt.Horizontal)
    self.slider.setTickPosition(qt.QSlider.TicksBothSides)
    self.slider.setTickInterval(10)
    self.slider.setSingleStep(1)
    self.slider.setMaximum(100)
    self.slider.setMinimum(-100)

    # combo box to be populated with list of PC values
    self.comboBox=qt.QComboBox()

    # spin box to display scaling
    self.spinBox=qt.QSpinBox()
    self.spinBox.setMaximum(100)
    self.spinBox.setMinimum(-100)

    # connect to eachother
    self.slider.valueChanged.connect(self.spinBox.setValue)
    self.spinBox.valueChanged.connect(self.slider.setValue)
    # self.label.connect(self.comboBox ,self.comboBox.currentIndexChanged, self.label.setText('test1'))

    # layout
    slidersLayout = qt.QGridLayout()
    slidersLayout.addWidget(self.slider,1,2)
    slidersLayout.addWidget(self.comboBox,1,1)
    slidersLayout.addWidget(self.spinBox,1,3)
    self.setLayout(slidersLayout) 

  
    
    

class LMData:
  def __init__(self):
    self.lm=0
    self.lmRaw=0
    self.lmOrig=0
    self.val=0
    self.vec=0
    self.alignCoords=0
    self.mShape=0
    self.tangentCoord=0
    self.shift=0
    self.centriodSize=0

  def calcLMVariation(self, SampleScaleFactor):
    i,j,k=self.lmRaw.shape
    varianceMat=np.zeros((i,j))
    for subject in range(k):
      tmp=pow((self.lmRaw[:,:,subject]-self.mShape),2)
      varianceMat=varianceMat+tmp
    varianceMat = SampleScaleFactor*np.sqrt(varianceMat/(k-1))
    return varianceMat
    
  def doGpa(self,skipScalingCheckBox):
    i,j,k=self.lmRaw.shape
    self.centriodSize=np.zeros(k)
    for i in range(k):
      self.centriodSize[i]=np.linalg.norm(self.lmRaw[:,:,i]-self.lmRaw[:,:,i].mean(axis=0))
    if skipScalingCheckBox:
      print "Skipping Scaling"
      self.lm, self.mShape=gpa_lib.doGPANoScale(self.lmRaw)
    else:
      self.lm, self.mShape=gpa_lib.doGPA(self.lmRaw)

  def calcEigen(self):
    twoDim=gpa_lib.makeTwoDim(self.lm)
    #mShape=gpa_lib.calcMean(twoDim)
    covMatrix=gpa_lib.calcCov(twoDim)
    self.val, self.vec=np.linalg.eig(covMatrix)
    self.vec=np.real(self.vec) 
    # scale eigen Vectors
    i,j =self.vec.shape
    # for q in range(j):
    #     self.vec[:,q]=self.vec[:,q]/np.linalg.norm(self.vec[:,q])

  def ExpandAlongPCs(self, numVec,scaleFactor,SampleScaleFactor):
    b=0
    i,j,k=self.lm.shape 
    print i,j,k
    tmp=np.zeros((i,j)) 
    points=np.zeros((i,j))   
    self.vec=np.real(self.vec)  
    # scale eigenvector
    for y in range(len(numVec)):
        if numVec[y] is not 0:
          #print numVec[y], scaleFactor[y]
          pcComponent = numVec[y] - 1 
          tmp[:,0]=tmp[:,0]+float(scaleFactor[y])*self.vec[0:i,pcComponent]*SampleScaleFactor
          tmp[:,1]=tmp[:,1]+float(scaleFactor[y])*self.vec[i:2*i,pcComponent]*SampleScaleFactor
          tmp[:,2]=tmp[:,2]+float(scaleFactor[y])*self.vec[2*i:3*i,pcComponent]*SampleScaleFactor
    
    self.shift=tmp

  def writeOutData(self,outputFolder,files):
    np.savetxt(outputFolder+os.sep+"MeanShape.csv", self.mShape, delimiter=",")
    np.savetxt(outputFolder+os.sep+"eigenvector.csv", self.vec, delimiter=",")
    np.savetxt(outputFolder+os.sep+"eigenvalues.csv", self.val, delimiter=",")

    percentVar=self.val/self.val.sum()
    self.procdist=gpa_lib.procDist(self.lm, self.mShape)
    files=np.array(files)
    i=files.shape
    files=files.reshape(i[0],1)
    k,j,i=self.lmRaw.shape

    coords=gpa_lib.makeTwoDim(self.lm)
    self.procdist=self.procdist.reshape(i,1)
    self.centriodSize=self.centriodSize.reshape(i,1)
    tmp=np.column_stack((files, self.procdist, self.centriodSize, np.transpose(coords)))
    header=np.array(['Sample_name','proc_dist','centeroid'])
    i1,j=tmp.shape
    coodrsL=(j-3)/3.0
    l=np.zeros(int(3*coodrsL))

    l=list(l)

    for x in range(int(coodrsL)):
      loc=x+1
      l[3*x]="x"+str(loc)
      l[3*x+1]="y"+str(loc)
      l[3*x+2]="z"+str(loc)
    l=np.array(l)
    header=np.column_stack((header.reshape(1,3),l.reshape(1,int(3*coodrsL))))
    tmp1=np.vstack((header,tmp))
    np.savetxt(outputFolder+os.sep+"OutputData.csv", tmp1, fmt="%s" , delimiter=",")

    # calc PC scores
    twoDcoors=gpa_lib.makeTwoDim(self.lm)
    scores=np.dot(np.transpose(twoDcoors),self.vec)
    scores=np.transpose(np.real(scores))
    
    scores=np.vstack((files.reshape(1,i),scores))
    np.savetxt(outputFolder+os.sep+"pcScores.csv", scores, fmt="%s", delimiter=",")

  def closestSample(self,files):
    import operator
    min_index, min_value = min(enumerate(self.procdist), key=operator.itemgetter(1))
    tmp=files[min_index]
    return tmp

  def calcEndpoints(self,LM,pc, scaleFactor, MonsterObj):
    i,j=LM.shape
    tmp=np.zeros((i,j))
    tmp[:,0]=self.vec[0:i,pc]
    tmp[:,1]=self.vec[i:2*i,pc]
    tmp[:,2]=self.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3.0

class GPAWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """
  def assignLayoutDescription(self): 
    customLayout1 = """
      <layout type=\"vertical\" split=\"true\" >
       <item splitSize=\"500\">
         <layout type=\"horizontal\">
           <item>
            <view class=\"vtkMRMLViewNode\" singletontag=\"GPA_1\">
             <property name=\"viewlabel\" action=\"default\">1</property>
            </view>
           </item>
           <item>
            <view class=\"vtkMRMLViewNode\" singletontag=\"GPA_2\" type=\"secondary\">"
             <property name=\"viewlabel\" action=\"default\">2</property>"
            </view>
          </item>
         </layout>
       </item>
       <item splitSize=\"500\">
        <layout type=\"horizontal\">
         <item>
          <view class=\"vtkMRMLSliceNode\" singletontag=\"Red\">
           <property name=\"orientation\" action=\"default\">Axial</property>
           <property name=\"viewlabel\" action=\"default\">R</property>
           <property name=\"viewcolor\" action=\"default\">#F34A33</property>
          </view>
         </item>
           <item>
            <view class=\"vtkMRMLPlotViewNode\" singletontag=\"PlotViewerWindow_1\">
             <property name=\"viewlabel\" action=\"default\">1</property>
            </view>
           </item>
         <item>
          <view class=\"vtkMRMLTableViewNode\" singletontag=\"TableViewerWindow_1\">"
           <property name=\"viewlabel\" action=\"default\">T</property>"
          </view>"
         </item>"
        </layout>
       </item>
      </layout>
     """
    customLayoutId1=5489
    layoutManager = slicer.app.layoutManager()
    layoutManager.layoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId1, customLayout1)                                         
    layoutManager.setLayout(customLayoutId1)
    
    # check for loaded reference model
    if hasattr(self, 'modelDisplayNode'):
      print "applying layout"
      viewNode1 = slicer.mrmlScene.GetFirstNodeByName("ViewGPA_1") #"View"+ singletonTag
      viewNode2 = slicer.mrmlScene.GetFirstNodeByName("ViewGPA_2")
      viewNodeSlice = slicer.mrmlScene.GetFirstNodeByName("Red")
      self.modelDisplayNode.SetViewNodeIDs([viewNode1.GetID()])
      self.cloneModelDisplayNode.SetViewNodeIDs([viewNode2.GetID()])
            
  def textIn(self,label, dispText, toolTip):
    """ a function to set up the appearnce of a QlineEdit widget.
    the widget is returned.
    """
    # set up text line
    textInLine=qt.QLineEdit();
    textInLine.setText(dispText)
    textInLine.toolTip = toolTip
    # set up label
    lineLabel=qt.QLabel()
    lineLabel.setText(label)

    # make clickable button
    button=qt.QPushButton("..")
    return textInLine, lineLabel, button  
    
  def selectLandmarkFile(self):
    self.LM_dir_name=qt.QFileDialog().getExistingDirectory()
    self.LMText.setText(self.LM_dir_name)
      
  def selectOutputDirectory(self):
    self.outputDirectory=qt.QFileDialog().getExistingDirectory()
    self.outText.setText(self.outputDirectory)

  def updateList(self):
    i,j,k=self.LM.lm.shape
    self.PCList=[]
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.slider3.populateComboBox(self.PCList)
    self.slider4.populateComboBox(self.PCList)
    self.slider5.populateComboBox(self.PCList)
    self.PCList.append('None')
    self.LM.val=np.real(self.LM.val)
    percentVar=self.LM.val/self.LM.val.sum()
    #percentVar=np.real(percentVar)
    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    self.vectorOne.addItem('None')
    self.vectorTwo.addItem('None')
    self.vectorThree.addItem('None')
    for x in range(10):
      tmp="{:.1f}".format(percentVar[x]*100) 
      string='PC '+str(x+1)+': '+str(tmp)+"%" +" var"
      self.PCList.append(string)
      self.XcomboBox.addItem(string)
      self.YcomboBox.addItem(string)
      self.vectorOne.addItem(string)
      self.vectorTwo.addItem(string)
      self.vectorThree.addItem(string)
    self.slider1.populateComboBox(self.PCList)
    self.slider2.populateComboBox(self.PCList)
    self.slider3.populateComboBox(self.PCList)
    self.slider4.populateComboBox(self.PCList)
    self.slider5.populateComboBox(self.PCList)

  def onLoad(self):
    logic = GPALogic()
    self.LM=LMData()
    lmToExclude=self.excludeLMText.text
    if len(lmToExclude) != 0:
      self.LMExclusionList=lmToExclude.split(",")
      print("Number of excluded landmarks: ", len(self.LMExclusionList))
      self.LMExclusionList=[np.int(x) for x in self.LMExclusionList]
      lmNP=np.asarray(self.LMExclusionList)
    else:
      self.LMExclusionList=[]
    self.LM.lmOrig, self.files = logic.mergeMatchs(self.LM_dir_name, self.LMExclusionList)
    self.LM.lmRaw, self.files = logic.mergeMatchs(self.LM_dir_name, self.LMExclusionList)
    shape = self.LM.lmOrig.shape
    print('Loaded ' + str(shape[2]) + ' subjects with ' + str(shape[0]) + ' landmark points.')
    #set scaling factor using mean of raw landmarks
    rawMeanLandmarks = self.LM.lmOrig.mean(2)
    logic = GPALogic()
    self.sampleSizeScaleFactor = logic.dist2(rawMeanLandmarks).max()
    print("Scale Factor: " + str(self.sampleSizeScaleFactor))
    
    self.LM.doGpa(self.skipScalingCheckBox.checked)
    self.LM.calcEigen()
    self.updateList()
    dateTimeStamp = datetime.now().strftime('%Y-%m-%d_%H_%M_%S')
    self.outputFolder = os.path.join(self.outputDirectory, dateTimeStamp)
    os.makedirs(self.outputFolder)
    self.LM.writeOutData(self.outputFolder, self.files)
    filename=self.LM.closestSample(self.files)
    self.populateDistanceTable(self.files)
    print("Closest sample to mean:" + filename)
  
    
  def populateDistanceTable(self, files):
    sortedArray = np.zeros(len(files), dtype={'names':('filename', 'procdist'),'formats':('U10','f8')})
    sortedArray['filename']=files
    sortedArray['procdist']=self.LM.procdist[:,0]
    sortedArray.sort(order='procdist')
    
  
    tableNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTableNode', 'Procrustes Distance Table')
    col1=tableNode.AddColumn()
    col1.SetName('ID')
    
    col2=tableNode.AddColumn()
    col2.SetName('Procrustes Distance')
    tableNode.SetColumnType('ID',vtk.VTK_STRING)
    tableNode.SetColumnType('Procrustes Distance',vtk.VTK_FLOAT)

    for i in range(len(files)):
      tableNode.AddEmptyRow()
      tableNode.SetCellText(i,0,sortedArray['filename'][i])
      tableNode.SetCellText(i,1,str(sortedArray['procdist'][i]))

    barPlot = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLPlotSeriesNode', 'Distances')
    barPlot.SetAndObserveTableNodeID(tableNode.GetID())
    barPlot.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeBar)
    barPlot.SetLabelColumnName('ID') #displayed when hovering mouse
    barPlot.SetYColumnName('Procrustes Distance') # for bar plots, index is the x-value
    chartNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLPlotChartNode', 'Procrustes Distance Chart')
    chartNode.SetTitle('Procrustes Distances')
    chartNode.SetLegendVisibility(False)
    chartNode.SetYAxisTitle('Distance')
    chartNode.SetXAxisTitle('Subjects')
    chartNode.AddAndObservePlotSeriesNodeID(barPlot.GetID())
    layoutManager = slicer.app.layoutManager()
    self.assignLayoutDescription()
    #set up custom layout
    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(chartNode.GetID())
    #add table to new layout
    slicer.app.applicationLogic().GetSelectionNode().SetReferenceActiveTableID(tableNode.GetID())
    slicer.app.applicationLogic().PropagateTableSelection()
	
	
  def lollipopTwoDPlotNewest(self, componentNumber): 
    points,dims = self.LM.mShape.shape
    endpoints=self.LM.calcEndpoints(self.LM.mShape,componentNumber-1,1,self.LM)
    logic = GPALogic()
    targetLMVTK=logic.convertNumpyToVTK(endpoints)
    sourceLMVTK=logic.convertNumpyToVTK(self.LM.mShape)
    
    #Set up TPS
    VTKTPS = vtk.vtkThinPlateSplineTransform()
    VTKTPS.SetSourceLandmarks( sourceLMVTK )
    VTKTPS.SetTargetLandmarks( targetLMVTK )
    VTKTPS.SetBasisToR()  # for 3D transform
    lolliplotTransformNode=slicer.mrmlScene.GetFirstNodeByName('Lolliplot Transform')
    
    if lolliplotTransformNode is None:
      lolliplotTransformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'Lolliplot Transform')
    
    lolliplotTransformNode.SetAndObserveTransformToParent(VTKTPS)

  def plot(self):
    logic = GPALogic()
    try:
      # get values from boxs
      xValue=self.XcomboBox.currentIndex
      yValue=self.YcomboBox.currentIndex

      # get data to plot
      data=gpa_lib.plotTanProj(self.LM.lm,xValue,yValue)

      # plot it
      logic.makeScatterPlot(data,self.files,'PCA Scatter Plots',"PC"+str(xValue+1),"PC"+str(yValue+1))
      self.assignLayoutDescription()
      
    except AttributeError:
      qt.QMessageBox.critical(
      slicer.util.mainWindow(),
      'Error', 'Please make sure a Landmark folder has been loaded!')

  def lolliPlot(self):
    pb1=self.vectorOne.currentIndex
    pb2=self.vectorTwo.currentIndex
    pb3=self.vectorThree.currentIndex

    pcList=[pb1,pb2,pb3]
    logic = GPALogic()
    #check if reference landmarks are loaded, otherwise use mean landmark positions to plot lollipops
    #later may update this to if self.sourceLMnumpy array is empty
    #if self.ThreeDType.isChecked(): #for 3D plot in the volume viewer window
    try:
      referenceLandmarks = logic.convertFudicialToNP(self.sourceLMNode)
    except AttributeError:
      referenceLandmarks = self.LM.lmOrig.mean(2)
      print("No reference landmarks loaded, plotting lollipop vectors at mean landmarks points.")
    componentNumber = 1
    for pc in pcList:
      logic.lollipopGraph(self.LM, referenceLandmarks, pc, self.sampleSizeScaleFactor, componentNumber, self.ThreeDType.isChecked())
      componentNumber+=1
    self.assignLayoutDescription()
      
      
    #else: #for a 2D plot in the chart window
    #  self.lollipopTwoDPlotNewest(pb1)
  
    
  def reset(self):
    # delete the two data objects

    # reset text fields
    self.outputDirectory=None
    self.outText.setText(" ")
    self.LM_dir_name=None
    self.LMText.setText(" ")

    self.slider1.clear()
    self.slider2.clear()
    self.slider3.clear()
    self.slider4.clear()
    self.slider5.clear()

    self.vectorOne.clear()
    self.vectorTwo.clear()
    self.vectorThree.clear()
    self.XcomboBox.clear()
    self.YcomboBox.clear()

    try:
      if self.LM is not None:
        del self.LM
    except:
      pass
    try:
      if self.volumes is not None:
        del self.volumes
    except:
      pass
    slicer.mrmlScene.Clear(0)
    # could delete created volumes and chart nodes  
    
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)
    # self.input_file=[]
    self.StyleSheet="font: 12px;  min-height: 20 px ; background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f6f7fa, stop: 1 #dadbde); border: 1px solid; border-radius: 4px; "
       
    inbutton=ctk.ctkCollapsibleButton()
    inbutton.text="Setup Analysis"
    inputLayout= qt.QGridLayout(inbutton)

    self.LMText, volumeInLabel, self.LMbutton=self.textIn('Landmark Folder','', '')
    inputLayout.addWidget(self.LMText,1,2)
    inputLayout.addWidget(volumeInLabel,1,1)
    inputLayout.addWidget(self.LMbutton,1,3)
    self.layout.addWidget(inbutton)
    self.LMbutton.connect('clicked(bool)', self.selectLandmarkFile)
    
    # Select output directory
    self.outText, outLabel, self.outbutton=self.textIn('Output directory prefix','', '')
    inputLayout.addWidget(self.outText,2,2)
    inputLayout.addWidget(outLabel,2,1)
    inputLayout.addWidget(self.outbutton,2,3)
    self.layout.addWidget(inbutton)
    self.outbutton.connect('clicked(bool)', self.selectOutputDirectory)

    self.excludeLMLabel=qt.QLabel('Exclude landmarks')
    inputLayout.addWidget(self.excludeLMLabel,3,1)

    self.excludeLMText=qt.QLineEdit()
    self.excludeLMText.setToolTip("No spaces. Seperate numbers by commas.  Example:  51,52")
    inputLayout.addWidget(self.excludeLMText,3,2,1,2)
    
    self.skipScalingCheckBox = qt.QCheckBox()
    self.skipScalingCheckBox.setText("Skip Scaling during GPA")
    self.skipScalingCheckBox.checked = 0
    self.skipScalingCheckBox.setToolTip("If checked, GPA will skip scaling.")
    inputLayout.addWidget(self.skipScalingCheckBox, 4,2)
    
    # node selector tab
    volumeButton=ctk.ctkCollapsibleButton()
    volumeButton.text="Setup 3D Visualization"
    volumeLayout= qt.QGridLayout(volumeButton)

    self.grayscaleSelectorLabel = qt.QLabel("Specify Reference Model for 3D Vis.")
    self.grayscaleSelectorLabel.setToolTip( "Select the model node for display")
    volumeLayout.addWidget(self.grayscaleSelectorLabel,1,1)

    self.grayscaleSelector = slicer.qMRMLNodeComboBox()
    self.grayscaleSelector.nodeTypes = ( ("vtkMRMLModelNode"), "" )
    #self.grayscaleSelector.addAttribute( "vtkMRMLModelNode", "LabelMap", 0 )
    self.grayscaleSelector.selectNodeUponCreation = False
    self.grayscaleSelector.addEnabled = False
    self.grayscaleSelector.removeEnabled = False
    self.grayscaleSelector.noneEnabled = True
    self.grayscaleSelector.showHidden = False
    #self.grayscaleSelector.showChildNodeTypes = False
    self.grayscaleSelector.setMRMLScene( slicer.mrmlScene )
    volumeLayout.addWidget(self.grayscaleSelector,1,2,1,3)


    self.FudSelectLabel = qt.QLabel("Landmark List: ")
    self.FudSelectLabel.setToolTip( "Select the glandmark list")
    self.FudSelect = slicer.qMRMLNodeComboBox()
    self.FudSelect.nodeTypes = ( ('vtkMRMLMarkupsFiducialNode'), "" )
    #self.FudSelect.addAttribute( "vtkMRMLScalarVolumeNode", "LabelMap", 0 )
    self.FudSelect.selectNodeUponCreation = False
    self.FudSelect.addEnabled = False
    self.FudSelect.removeEnabled = False
    self.FudSelect.noneEnabled = True
    self.FudSelect.showHidden = False
    self.FudSelect.showChildNodeTypes = False
    self.FudSelect.setMRMLScene( slicer.mrmlScene )
    volumeLayout.addWidget(self.FudSelectLabel,2,1)
    volumeLayout.addWidget(self.FudSelect,2,2,1,3)

    
    selectorButton = qt.QPushButton("Select")
    selectorButton.checkable = True
    selectorButton.setStyleSheet(self.StyleSheet)
    volumeLayout.addWidget(selectorButton,3,1,1,4)
    selectorButton.connect('clicked(bool)', self.onSelect)

    self.layout.addWidget(volumeButton)

    #Apply Button 
    loadButton = qt.QPushButton("Execute GPA + PCA")
    loadButton.checkable = True
    loadButton.setStyleSheet(self.StyleSheet)
    inputLayout.addWidget(loadButton,5,1,1,3)
    loadButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    loadButton.connect('clicked(bool)', self.onLoad)

    #PC plot section
    plotFrame=ctk.ctkCollapsibleButton()
    plotFrame.text="PCA Scatter Plot Options"
    plotLayout= qt.QGridLayout(plotFrame)
    self.layout.addWidget(plotFrame)

    self.XcomboBox=qt.QComboBox()
    Xlabel=qt.QLabel("X Axis")
    plotLayout.addWidget(Xlabel,1,1)
    plotLayout.addWidget(self.XcomboBox,1,2,1,3)

    self.YcomboBox=qt.QComboBox()
    Ylabel=qt.QLabel("Y Axis")
    plotLayout.addWidget(Ylabel,2,1)
    plotLayout.addWidget(self.YcomboBox,2,2,1,3)

    plotButton = qt.QPushButton("Scatter Plot")
    plotButton.checkable = True
    plotButton.setStyleSheet(self.StyleSheet)
    plotButton.toolTip = "Plot PCs"
    plotLayout.addWidget(plotButton,3,1,1,4)
    plotButton.connect('clicked(bool)', self.plot)

    # Lollipop Plot Section

    lolliFrame=ctk.ctkCollapsibleButton()
    lolliFrame.text="Lollipop Plot Options"
    lolliLayout= qt.QGridLayout(lolliFrame)
    self.layout.addWidget(lolliFrame)

    self.vectorOne=qt.QComboBox()
    vectorOneLabel=qt.QLabel("Vector One: Red")
    lolliLayout.addWidget(vectorOneLabel,1,1)
    lolliLayout.addWidget(self.vectorOne,1,2,1,3)

    self.vectorTwo=qt.QComboBox()
    vector2Label=qt.QLabel("Vector Two: Green")
    lolliLayout.addWidget(vector2Label,2,1)
    lolliLayout.addWidget(self.vectorTwo,2,2,1,3)

    self.vectorThree=qt.QComboBox()
    vector3Label=qt.QLabel("Vector Three: Blue")
    lolliLayout.addWidget(vector3Label,3,1)
    lolliLayout.addWidget(self.vectorThree,3,2,1,3)
    
    self.ThreeDType=qt.QRadioButton()
    ThreeDTypeLabel=qt.QLabel("3D Plot")
    self.ThreeDType.setChecked(True)
    lolliLayout.addWidget(ThreeDTypeLabel,4,1)
    lolliLayout.addWidget(self.ThreeDType,4,2,1,2)
    self.TwoDType=qt.QRadioButton()
    TwoDTypeLabel=qt.QLabel("2D Plot")
    lolliLayout.addWidget(TwoDTypeLabel,4,4)
    lolliLayout.addWidget(self.TwoDType,4,5,1,2)

    lolliButton = qt.QPushButton("Lollipop Vector Plot")
    lolliButton.checkable = True
    lolliButton.setStyleSheet(self.StyleSheet)
    lolliButton.toolTip = "Plot PC vectors"
    lolliLayout.addWidget(lolliButton,5,1,1,6)
    lolliButton.connect('clicked(bool)', self.lolliPlot)
 
 # Landmark Distribution Section
    distributionFrame=ctk.ctkCollapsibleButton()
    distributionFrame.text="Landmark Distribution Plot Options"
    distributionLayout= qt.QGridLayout(distributionFrame)
    self.layout.addWidget(distributionFrame)

    self.EllipseType=qt.QRadioButton()
    ellipseTypeLabel=qt.QLabel("Ellipse type")
    self.EllipseType.setChecked(True)
    distributionLayout.addWidget(ellipseTypeLabel,2,1)
    distributionLayout.addWidget(self.EllipseType,2,2,1,2)
    self.SphereType=qt.QRadioButton()
    sphereTypeLabel=qt.QLabel("Sphere type")
    distributionLayout.addWidget(sphereTypeLabel,3,1)
    distributionLayout.addWidget(self.SphereType,3,2,1,2)
    self.CloudType=qt.QRadioButton()
    cloudTypeLabel=qt.QLabel("Point cloud type")
    distributionLayout.addWidget(cloudTypeLabel,4,1)
    distributionLayout.addWidget(self.CloudType,4,2,1,2)
    
    self.scaleSlider = ctk.ctkSliderWidget()
    self.scaleSlider.singleStep = 1
    self.scaleSlider.minimum = 1
    self.scaleSlider.maximum = 10
    self.scaleSlider.value = 5
    self.scaleSlider.setToolTip("Set scale for variance visualization")
    sliderLabel=qt.QLabel("Scale Glyphs")
    distributionLayout.addWidget(sliderLabel,5,1)
    distributionLayout.addWidget(self.scaleSlider,5,2,1,2)
    
    plotDistributionButton = qt.QPushButton("Plot LM Distribution")
    plotDistributionButton.checkable = True
    plotDistributionButton.setStyleSheet(self.StyleSheet)
    plotDistributionButton.toolTip = "Visualize distribution of landmarks from all subjects"
    distributionLayout.addWidget(plotDistributionButton,6,1,1,4)
    plotDistributionButton.connect('clicked(bool)', self.onPlotDistribution)
    
    # PC warping
    vis=ctk.ctkCollapsibleButton()
    vis.text='PCA Visualization Parameters'
    visLayout= qt.QGridLayout(vis)

    self.PCList=[]
    self.slider1=sliderGroup()
    self.slider1.connectList(self.PCList)
    visLayout.addWidget(self.slider1,3,1,1,2)

    self.slider2=sliderGroup()
    self.slider2.connectList(self.PCList)
    visLayout.addWidget(self.slider2,4,1,1,2)

    self.slider3=sliderGroup()
    self.slider3.connectList(self.PCList)
    visLayout.addWidget(self.slider3,5,1,1,2)

    self.slider4=sliderGroup()
    self.slider4.connectList(self.PCList)
    visLayout.addWidget(self.slider4,6,1,1,2)

    self.slider5=sliderGroup()
    self.slider5.connectList(self.PCList)
    visLayout.addWidget(self.slider5,7,1,1,2)

    self.layout.addWidget(vis)

        
    #Apply Button 
    applyButton = qt.QPushButton("Apply")
    applyButton.checkable = True
    applyButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(applyButton)
    applyButton.toolTip = "Push to start the program. Make sure you have filled in all the data."
    applyFrame=qt.QFrame(self.parent)
    applyButton.connect('clicked(bool)', self.onApply)
    visLayout.addWidget(applyButton,8,1,1,2)
    resetButton = qt.QPushButton("Reset Scene")
    resetButton.checkable = True
    resetButton.setStyleSheet(self.StyleSheet)
    self.layout.addWidget(resetButton)
    resetButton.toolTip = "Push to reset all fields."
    resetButton.connect('clicked(bool)', self.reset)

    self.layout.addStretch(1)

    
  def cleanup(self):
    pass

  def onSelect(self):
    self.modelNode=self.grayscaleSelector.currentNode()
    self.modelDisplayNode = self.modelNode.GetDisplayNode()
    
    #define a reference model as clone of selected volume
    shNode = slicer.vtkMRMLSubjectHierarchyNode.GetSubjectHierarchyNode(slicer.mrmlScene)
    itemIDToClone = shNode.GetItemByDataNode(self.modelNode)
    clonedItemID = slicer.modules.subjecthierarchy.logic().CloneSubjectHierarchyItem(shNode, itemIDToClone)
    self.cloneModelNode = shNode.GetItemDataNode(clonedItemID)
    self.cloneModelNode.SetName("GPA Reference Volume")
    self.cloneModelDisplayNode = self.cloneModelNode.GetDisplayNode()
    self.cloneModelDisplayNode.SetColor(0,0,1)
    
    #select landmarks
    logic = GPALogic()
    self.sourceLMNode=self.FudSelect.currentNode()
    self.sourceLMnumpy=logic.convertFudicialToNP(self.sourceLMNode)
    
    #remove any excluded landmarks
    j=len(self.LMExclusionList)
    if(j != 0):
      for i in range(j):
        self.sourceLMnumpy = np.delete(self.sourceLMnumpy,(np.int(self.LMExclusionList[i])-1),axis=0)
        
    self.transformNode=slicer.mrmlScene.GetFirstNodeByName('TPS Transform')
    if self.transformNode is None:
      self.transformNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLTransformNode', 'TPS Transform')
    #apply custom layout
    self.assignLayoutDescription()
    

  def onApply(self):
    pc1=self.slider1.boxValue()
    pc2=self.slider2.boxValue()
    pc3=self.slider3.boxValue()
    pc4=self.slider4.boxValue()
    pc5=self.slider5.boxValue()
    pcSelected=[pc1,pc2,pc3,pc4,pc5]

    # get scale values for each pc.
    sf1=self.slider1.sliderValue()
    sf2=self.slider2.sliderValue()
    sf3=self.slider3.sliderValue()
    sf4=self.slider4.sliderValue()
    sf5=self.slider5.sliderValue()
    scaleFactors=np.zeros((5))
    scaleFactors[0]=sf1/100.0
    scaleFactors[1]=sf2/100.0
    scaleFactors[2]=sf3/100.0
    scaleFactors[3]=sf4/100.0
    scaleFactors[4]=sf5/100.0

    j=0
    for i in pcSelected:
      if i==0:
       scaleFactors[j]=0.0
      j=j+1

    logic = GPALogic()
    #get target landmarks
    self.LM.ExpandAlongPCs(pcSelected,scaleFactors, self.sampleSizeScaleFactor)
    #sourceLMNP=logic.convertFudicialToNP(self.sourceLMNode)
    
    #target=endpoints
    target=self.sourceLMnumpy+self.LM.shift
    targetLMVTK=logic.convertNumpyToVTK(target)
    sourceLMVTK=logic.convertNumpyToVTK(self.sourceLMnumpy)
    
    #Set up TPS
    VTKTPS = vtk.vtkThinPlateSplineTransform()
    VTKTPS.SetSourceLandmarks( sourceLMVTK )
    VTKTPS.SetTargetLandmarks( targetLMVTK )
    VTKTPS.SetBasisToR()  # for 3D transform

    #Connect transform to model
    self.transformNode.SetAndObserveTransformToParent( VTKTPS )
    self.modelNode.SetAndObserveTransformNodeID(self.transformNode.GetID())
    #slicer.app.layoutManager().setLayout(slicer.vtkMRMLLayoutNode.SlicerLayoutConventionalPlotView)
    #slicer.app.layoutManager.LayoutLogic().GetLayoutNode().AddLayoutDescription(customLayoutId1, customLayout1)                                         
    #slicer.app.layoutManager.setLayout(customLayoutId1)
    self.assignLayoutDescription()
    

  def onPlotDistribution(self):
    if self.CloudType.isChecked():
      self.plotDistributionCloud()
    else: 
      self.plotDistributionGlyph(self.scaleSlider.value)
      
    self.assignLayoutDescription()
    
      
  def plotDistributionCloud(self):
    i,j,k=self.LM.lmRaw.shape
    pt=[0,0,0]
    #set up vtk point array for each landmark point
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(i*k)
    indexes = vtk.vtkDoubleArray()
    indexes.SetName('LM Index')
    pointCounter = 0
   
    for subject in range(0,k):
      for landmark in range(0,i):
        pt=self.LM.lmOrig[landmark,:,subject]
        points.SetPoint(pointCounter,pt)
        indexes.InsertNextValue(landmark)
        pointCounter+=1
    
    #add points to polydata
    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().SetScalars(indexes)
    
    #set up glyph for visualizing point cloud
    sphereSource = vtk.vtkSphereSource()
    glyph = vtk.vtkGlyph3D()
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)   
    glyph.ScalingOff()    
    glyph.Update()
  
    #display
    modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Point Cloud')
    if modelNode is None:
      modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', 'Landmark Point Cloud')
      modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
      modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
    
    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('LM Index')
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')

    modelNode.SetAndObservePolyData(glyph.GetOutput())
    
  def plotDistributionGlyph(self, sliderScale):
    varianceMat = self.LM.calcLMVariation(self.sampleSizeScaleFactor)
    i,j,k=self.LM.lmRaw.shape
    pt=[0,0,0]
    #set up vtk point array for each landmark point
    points = vtk.vtkPoints()
    points.SetNumberOfPoints(i)
    scales = vtk.vtkDoubleArray()
    scales.SetName("Scales")
    index = vtk.vtkDoubleArray()
    index.SetName("Index")

    #set up tensor array to scale ellipses
    tensors = vtk.vtkDoubleArray()
    tensors.SetNumberOfTuples(i)
    tensors.SetNumberOfComponents(9)
    tensors.SetName("Tensors")
    
    #check if reference landmarks are loaded
    try:
      referenceLandmarks = self.sourceLMnumpy
    except AttributeError:
      referenceLandmarks = self.LM.lmOrig.mean(2)
      print("No reference landmarks loaded. Plotting distributions at mean landmark points.")
      print("mean landmarks: ", referenceLandmarks)
    for landmark in range(i):
      pt=referenceLandmarks[landmark,:]
      points.SetPoint(landmark,pt)
      scales.InsertNextValue(sliderScale*(varianceMat[landmark,0]+varianceMat[landmark,1]+varianceMat[landmark,2])/3)
      tensors.InsertTuple9(landmark,sliderScale*varianceMat[landmark,0],0,0,0,sliderScale*varianceMat[landmark,1],0,0,0,sliderScale*varianceMat[landmark,2])
      index.InsertNextValue(landmark)

    polydata=vtk.vtkPolyData()
    polydata.SetPoints(points)
    polydata.GetPointData().AddArray(index)

    if self.EllipseType.isChecked():
      polydata.GetPointData().SetScalars(index)
      polydata.GetPointData().SetTensors(tensors)
      glyph = vtk.vtkTensorGlyph()
      glyph.ExtractEigenvaluesOff()
      modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Ellipse')
      if modelNode is None:
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', 'Landmark Variance Ellipse')
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())

    else:
      polydata.GetPointData().SetScalars(scales)
      polydata.GetPointData().AddArray(index)
      glyph = vtk.vtkGlyph3D()
      modelNode=slicer.mrmlScene.GetFirstNodeByName('Landmark Variance Sphere')
      if modelNode is None:
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', 'Landmark Variance Sphere')
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
    
    sphereSource = vtk.vtkSphereSource()
    sphereSource.SetThetaResolution(64)
    sphereSource.SetPhiResolution(64)
    
    glyph.SetSourceConnection(sphereSource.GetOutputPort())
    glyph.SetInputData(polydata)
    glyph.Update()

    modelNode.SetAndObservePolyData(glyph.GetOutput())
    modelDisplayNode = modelNode.GetDisplayNode()
    modelDisplayNode.SetScalarVisibility(True)
    modelDisplayNode.SetActiveScalarName('Index') #color by landmark number 
    modelDisplayNode.SetAndObserveColorNodeID('vtkMRMLColorTableNodeFileColdToHotRainbow.txt')
    


#
# GPALogic
#

class GPALogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def hasImageData(self,volumeNode):
    """This is an example logic method that
    returns true if the passed in volume
    node has valid image data
    """
    if not volumeNode:
      logging.debug('hasImageData failed: no volume node')
      return False
    if volumeNode.GetImageData() is None:
      logging.debug('hasImageData failed: no image data in volume node')
      return False
    return True

  def isValidInputOutputData(self, inputVolumeNode, outputVolumeNode):
    """Validates if the output is not the same as input
    """
    if not inputVolumeNode:
      logging.debug('isValidInputOutputData failed: no input volume node defined')
      return False
    if not outputVolumeNode:
      logging.debug('isValidInputOutputData failed: no output volume node defined')
      return False
    if inputVolumeNode.GetID()==outputVolumeNode.GetID():
      logging.debug('isValidInputOutputData failed: input and output volume is the same. Create a new volume for output to avoid this error.')
      return False
    return True

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def mergeMatchs(self, topDir, lmToRemove, suffix=".fcsv"):
    # initial data array
    dirs, files=self.walk_dir(topDir)
    matchList, noMatch=self.createMatchList(topDir, "fcsv")
    landmarks=self.initDataArray(dirs,files[0],len(matchList))
    matchedfiles=[]
    for i in range(len(matchList)):
      tmp1=self.importLandMarks(matchList[i]+".fcsv")
      landmarks[:,:,i]=tmp1
      matchedfiles.append(os.path.basename(matchList[i]))
    j=len(lmToRemove)
    for i in range(j):
      landmarks=np.delete(landmarks,(np.int(lmToRemove[i])-1),axis=0)    
    return landmarks, matchedfiles
   
  def createMatchList(self, topDir,suffix): 
   #eliminate requirement for 2 landmark files
   #retains data structure in case filtering is required later.
    validFiles=[]
    for root, dirs, files in os.walk(topDir):
      for name in files:
        if fnmatch.fnmatch(name,"*"+suffix):
          validFiles.append(os.path.join(root, name[:-5]))
    invalidFiles=[]
    return validFiles, invalidFiles
    
  def importLandMarks(self, filePath):
    """Imports the landmarks from a .fcsv file. Does not import sample if a  landmark is -1000
    Adjusts the resolution is log(nhrd) file is found returns kXd array of landmark data. k=# of landmarks d=dimension
    """
    # import data file
    datafile=open(filePath,'r')
    data=[]
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):
        data.append(row.strip().split(','))
    # Make Landmark array
    dataArray=np.zeros(shape=(len(data),3))
    j=0
    sorter=[]
    for i in data:
      tmp=np.array(i)[1:4]
      dataArray[j,0:3]=tmp

      x=np.array(i).shape
      j=j+1
    slicer.app.processEvents()
    return dataArray

  def walk_dir(self, top_dir):
    """
    Returns a list of all fcsv files in a diriectory, including sub-directories.
    """
    dir_to_explore=[]
    file_to_open=[]
    for path, dir, files in os.walk(top_dir):
      for filename in files:
        if fnmatch.fnmatch(filename,"*.fcsv"):
          #print filename
          dir_to_explore.append(path)
          file_to_open.append(filename)
    return dir_to_explore, file_to_open

  def initDataArray(self, dirs, file,k):  
    """
    returns an np array for the storage of the landmarks.
    """
    j=3 
    # import data file
    datafile=open(dirs[0]+os.sep+file,'r')
    data=[]
    for row in datafile:
      if not fnmatch.fnmatch(row[0],"#*"):
        # print row
        data.append(row.strip().split(','))
    i= len(data)
    landmarks=np.zeros(shape=(i,j,k))
    return landmarks

  def importAllLandmarks(self, inputDirControl, outputFolder):
    """
    Import all of the landmarks.
    Controls are stored frist, then experimental landmarks, in a np array
    Returns the landmark array and the number of experimetnal and control samples repectively.
    """
    # get files and directories
    dirs, files=self.walk_dir(inputDirControl)
    # print dirs, files
    with open(outputFolder+os.sep+"filenames.txt",'w') as f:
      for i in range(len(files)):
        tmp=files[i]
        f.write(tmp[:-5]+"\n")
    # initilize and fill control landmakrs
    landmarksControl=self.initDataArray(dirs,files[0])
    iD,jD,kD=landmarksControl.shape
    nControl=kD
    iD=iD.__int__();jD=jD.__int__();kD=kD.__int__()
    # fill landmarks
    for i in range(0,len(files)):
      tmp=self.importLandMarks(dirs[i]+os.sep+files[i])
      #  check that landmarks where imported, if not delete zeros matrix
      if type(tmp) is not 'NoneType':
        it,at=tmp.shape
        it=it.__int__(); at=at.__int__()
        if it == iD and at == jD:
          landmarksControl[:,:,i]=tmp
        else:
          np.delete(landmarksControl,i,axis=2)
      else:
          np.delete(landmarksControl,i,axis=2)

    return landmarksControl, files

    # function with vtk and tps
    # Random Function
  def dist(self, a):
    """
    Computes the ecuideain distance matrix for nXK points in a 3D space. So the input matrix is nX3xk
    Returns a nXnXk matrix 
    """
    id,jd,kd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1,kd))
    dx=fnx(a[:,0,:])
    dy=fnx(a[:,1,:])
    dz=fnx(a[:,2,:])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

  def dist2(self, a):
    """
    Computes the ecuideain distance matrix for n points in a 3D space
    Returns a nXn matrix 
     """
    id,jd=a.shape
    fnx = lambda q : q - np.reshape(q, (id, 1))
    dx=fnx(a[:,0])
    dy=fnx(a[:,1])
    dz=fnx(a[:,2])
    return (dx**2.0+dy**2.0+dz**2.0)**0.5

  #plotting functions
  def makeScatterPlot(self, data, files, title,xAxis,yAxis):
    numPoints = len(data)
    #print(data.shape)
    tableNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLTableNode", 'PCA Scatter Plot Table')
    
    #set up columns for X,Y, and labels
    pcX=tableNode.AddColumn()
    pcX.SetName(xAxis)
    tableNode.SetColumnType(xAxis, vtk.VTK_FLOAT)
    
    pcY=tableNode.AddColumn()
    pcY.SetName(yAxis)
    tableNode.SetColumnType(yAxis, vtk.VTK_FLOAT)
    
    labels=tableNode.AddColumn()
    labels.SetName('Subject ID')
    tableNode.SetColumnType('Subject ID',vtk.VTK_STRING)

    for i in range(numPoints):
      tableNode.AddEmptyRow()
      tableNode.SetCellText(i, 0, str(data[i,0]))
      tableNode.SetCellText(i, 1, str(data[i,1]))
      tableNode.SetCellText(i,2,files[i])
      
    plotSeriesNode1 = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotSeriesNode", "Subjects")
    plotSeriesNode1.SetAndObserveTableNodeID(tableNode.GetID())
    plotSeriesNode1.SetXColumnName(xAxis)
    plotSeriesNode1.SetYColumnName(yAxis)
    plotSeriesNode1.SetLabelColumnName('Subject ID')
    plotSeriesNode1.SetPlotType(slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
    plotSeriesNode1.SetLineStyle(slicer.vtkMRMLPlotSeriesNode.LineStyleNone)
    plotSeriesNode1.SetMarkerStyle(slicer.vtkMRMLPlotSeriesNode.MarkerStyleSquare)
    plotSeriesNode1.SetUniqueColor()
     
    plotChartNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLPlotChartNode")
    plotChartNode.AddAndObservePlotSeriesNodeID(plotSeriesNode1.GetID())
    plotChartNode.SetTitle('PCA Scatter Plot ')
    plotChartNode.SetXAxisTitle(xAxis)
    plotChartNode.SetYAxisTitle(yAxis)
     
    layoutManager = slicer.app.layoutManager()

    plotWidget = layoutManager.plotWidget(0)
    plotViewNode = plotWidget.mrmlPlotViewNode()
    plotViewNode.SetPlotChartNodeID(plotChartNode.GetID())

  def lollipopGraph(self, LMObj,LM, pc, scaleFactor, componentNumber, ThreeDOption):
    # set options for 3 vector displays
    if componentNumber == 1:
      color = [1,0,0]
      modelNodeName = 'Lollipop Vector Plot 1'
    elif componentNumber == 2:
      color = [0,1,0]
      modelNodeName = 'Lollipop Vector Plot 2'
    else: 
      color = [0,0,1]
      modelNodeName = 'Lollipop Vector Plot 3'
    
    if pc is not 0:
      pc=pc-1 # get current component 
      endpoints=self.calcEndpoints(LMObj,LM,pc,scaleFactor)
      i,j=LM.shape
        
      # declare arrays for polydata
      points = vtk.vtkPoints() 
      points.SetNumberOfPoints(i*2)
      lines = vtk.vtkCellArray()
      magnitude = vtk.vtkFloatArray()
      magnitude.SetName('Magnitude');
      magnitude.SetNumberOfComponents(1);
      magnitude.SetNumberOfValues(i);
        
      for x in range(i): #populate vtkPoints and vtkLines
        points.SetPoint(x,LM[x,:])
        points.SetPoint(x+i,endpoints[x,:])
        line = vtk.vtkLine()
        line.GetPointIds().SetId(0,x)
        line.GetPointIds().SetId(1,x+i)
        lines.InsertNextCell(line)
        magnitude.InsertValue(x,abs(LM[x,0]-endpoints[x,0]) + abs(LM[x,1]-endpoints[x,1]) + abs(LM[x,2]-endpoints[x,2]))

      polydata=vtk.vtkPolyData()
      polydata.SetPoints(points)
      polydata.SetLines(lines)
      polydata.GetCellData().AddArray(magnitude)

      tubeFilter = vtk.vtkTubeFilter()
      tubeFilter.SetInputData(polydata)
      tubeFilter.SetRadius(0.7)
      tubeFilter.SetNumberOfSides(20)
      tubeFilter.CappingOn()
      tubeFilter.Update()
    
      #check if there is a model node for lollipop plot
      modelNode=slicer.mrmlScene.GetFirstNodeByName(modelNodeName)
      if modelNode is None:
        modelNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelNode', modelNodeName)
        modelDisplayNode = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLModelDisplayNode')
        modelNode.SetAndObserveDisplayNodeID(modelDisplayNode.GetID())
 
      modelDisplayNode = modelNode.GetDisplayNode()
      
      modelDisplayNode.SetColor(color)
      modelDisplayNode.SetSliceIntersectionVisibility(False)
      modelNode.SetDisplayVisibility(1)
      modelNode.SetAndObservePolyData(tubeFilter.GetOutput())
      if not ThreeDOption:
        modelDisplayNode.SetSliceDisplayModeToProjection()
        modelDisplayNode.SetSliceIntersectionVisibility(True)
    else:
      modelNode=slicer.mrmlScene.GetFirstNodeByName(modelNodeName)
      if modelNode is not None:
        modelNode.SetDisplayVisibility(0)
    
  def calcEndpoints(self,LMObj,LM,pc, scaleFactor):
    i,j=LM.shape
    print("LM shape: ", LM.shape)
    tmp=np.zeros((i,j))
    tmp[:,0]=LMObj.vec[0:i,pc]
    tmp[:,1]=LMObj.vec[i:2*i,pc]
    tmp[:,2]=LMObj.vec[2*i:3*i,pc]
    return LM+tmp*scaleFactor/3.0
    
  def convertFudicialToVTKPoint(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfFiducials()
    x=y=z=0
    loc=[x,y,z]
    lmData=np.zeros((numberOfLM,3))
    for i in range(numberOfLM):
      fnode.GetNthFiducialPosition(i,loc)
      lmData[i,:]=np.asarray(loc)
    #return lmData
    # print lmData
    points=vtk.vtkPoints()
    for i in range(numberOfLM):
      points.InsertNextPoint(lmData[i,0], lmData[i,1], lmData[i,2]) 
    return points

  def convertFudicialToNP(self, fnode):
    import numpy as np
    numberOfLM=fnode.GetNumberOfFiducials()
    x=y=z=0
    loc=[x,y,z]
    lmData=np.zeros((numberOfLM,3))
    # 
    for i in range(numberOfLM):
      fnode.GetNthFiducialPosition(i,loc)
      lmData[i,:]=np.asarray(loc)
    return lmData

  def convertNumpyToVTK(self, A):
    x,y=A.shape
    points=vtk.vtkPoints()
    for i in range(x):
      points.InsertNextPoint(A[i,0], A[i,1], A[i,2])
    return points

  def convertNumpyToVTKmatrix44(self, A):
    x,y=A.shape
    mat=vtk.vtkMatrix4x4()
    for i in range(x):
      for j in range(y):
        mat.SetElement(i,j,A[i,j])
    return mat

  def convertVTK44toNumpy(self, A):
    a=np.ones((4,4))
    for i in range(4):
      for j in range(4):
        a[i,j]=A.GetElement(i,j)
    return a


class GPATest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_GPA1()

  def test_GPA1(self):
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
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = GPALogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')