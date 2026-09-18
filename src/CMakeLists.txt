# src/CMakeLists.txt - Algorithm modules and shared infrastructure
# Algorithm targets (common, chaining, cuckoo, hopscotch, svc_hash) will be added in Phases 1-3.

# Shared include directory for all submodules
add_library(colliscope_interface INTERFACE)
target_include_directories(colliscope_interface INTERFACE ${CMAKE_CURRENT_SOURCE_DIR})
