cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(slicerNasalSeptumAnalysis)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/slicerNasalSeptumAnalysis")
set(EXTENSION_CATEGORY "NasalSeptumAnalysis")
set(EXTENSION_CONTRIBUTORS "Maxim Khabarov (SpbSU), Eugene Kalishenko (SpbSU)")
set(EXTENSION_DESCRIPTION "Plugin for nasal septum analysis")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/slicerNasalSeptumAnalysis.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/slicerNasalSeptumAnalysis/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(t_SegmentNasalSeptum)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
