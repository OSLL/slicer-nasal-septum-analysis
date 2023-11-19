cmake_minimum_required(VERSION 3.16.3...3.19.7 FATAL_ERROR)

project(nasal_septum_analysis)

#-----------------------------------------------------------------------------
# Extension meta-information
set(EXTENSION_HOMEPAGE "https://www.slicer.org/wiki/Documentation/Nightly/Extensions/nasal_septum_analysis")
set(EXTENSION_CATEGORY "Nasal Septum Analysis")
set(EXTENSION_CONTRIBUTORS "Maxim Khbarov (SpbSU), Eugene Kalishenko (SpbSU)")
set(EXTENSION_DESCRIPTION "Extension for nasal septum analysis
")
set(EXTENSION_ICONURL "https://www.example.com/Slicer/Extensions/nasal_septum_analysis.png")
set(EXTENSION_SCREENSHOTURLS "https://www.example.com/Slicer/Extensions/nasal_septum_analysis/Screenshots/1.png")
set(EXTENSION_DEPENDS "NA") # Specified as a list or "NA" if no dependencies

#-----------------------------------------------------------------------------
# Extension dependencies
find_package(Slicer REQUIRED)
include(${Slicer_USE_FILE})

#-----------------------------------------------------------------------------
# Extension modules
add_subdirectory(septum_analysis)
## NEXT_MODULE

#-----------------------------------------------------------------------------
include(${Slicer_EXTENSION_GENERATE_CONFIG})
include(${Slicer_EXTENSION_CPACK})
