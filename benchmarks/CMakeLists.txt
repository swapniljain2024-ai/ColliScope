# benchmarks/CMakeLists.txt - Benchmark engine library and CLI executable

add_library(colliscope_benchmark_engine STATIC
    benchmark_engine.cpp
)
target_include_directories(colliscope_benchmark_engine PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/src
)
target_link_libraries(colliscope_benchmark_engine PUBLIC
    colliscope_interface
    colliscope_svc_hash
    colliscope_chaining
    colliscope_cuckoo
    colliscope_hopscotch
)

add_executable(colliscope_bench
    benchmark_main.cpp
)
target_link_libraries(colliscope_bench PRIVATE
    colliscope_benchmark_engine
)
