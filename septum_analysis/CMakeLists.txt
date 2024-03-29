#-----------------------------------------------------------------------------
set(MODULE_NAME septum_analysis)

set(EXTENSION_DEPENDS "SegmentEditorLocalThreshold")

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  ${MODULE_NAME}.py
  ${MODULE_NAME}Lib/__init__.py
  ${MODULE_NAME}Lib/CalculatorVolume.py
  ${MODULE_NAME}Lib/CalculatorVolumeWidget.py
  ${MODULE_NAME}Lib/SelectingClosedSurfaceEditorEffect.py
  ${MODULE_NAME}Lib/PipelineApplierLogic.py
  ${MODULE_NAME}Lib/utils.py
  )

set(MODULE_PYTHON_RESOURCES
  Resources/Icons/${MODULE_NAME}.png
  Resources/UI/${MODULE_NAME}.ui
  )

#-----------------------------------------------------------------------------
slicerMacroBuildScriptedModule(
  NAME ${MODULE_NAME}
  SCRIPTS ${MODULE_PYTHON_SCRIPTS}
  RESOURCES ${MODULE_PYTHON_RESOURCES}
  WITH_GENERIC_TESTS
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)

  # Register the unittest subclass in the main script as a ctest.
  # Note that the test will also be available at runtime.
  slicer_add_python_unittest(SCRIPT ${MODULE_NAME}.py)

  # Additional build-time testing
  add_subdirectory(Testing)
endif()
