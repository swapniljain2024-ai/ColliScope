# src/CMakeLists.txt - Algorithm modules and shared infrastructure

# Shared include directory for all submodules
add_library(colliscope_interface INTERFACE)
target_include_directories(colliscope_interface INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/chaining
    ${CMAKE_CURRENT_SOURCE_DIR}/cuckoo
    ${CMAKE_CURRENT_SOURCE_DIR}/hopscotch
    ${CMAKE_CURRENT_SOURCE_DIR}/svc_hash
)

# SVC-Hash algorithm library (Phase 2)
add_library(colliscope_svc_hash STATIC
    svc_hash/svc_hash_table.cpp
)
target_link_libraries(colliscope_svc_hash PUBLIC colliscope_interface)

# Baseline algorithm libraries (Phase 3)
add_library(colliscope_chaining STATIC
    chaining/chaining_table.cpp
)
target_link_libraries(colliscope_chaining PUBLIC colliscope_interface)

add_library(colliscope_cuckoo STATIC
    cuckoo/cuckoo_table.cpp
)
target_link_libraries(colliscope_cuckoo PUBLIC colliscope_interface)

add_library(colliscope_hopscotch STATIC
    hopscotch/hopscotch_table.cpp
)
target_link_libraries(colliscope_hopscotch PUBLIC colliscope_interface)
