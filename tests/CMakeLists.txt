# tests/CMakeLists.txt - Test targets

# Phase 0 Scaffolding test (verifies toolchain sanity)
add_executable(test_scaffolding
    cpp/test_scaffolding.cpp
)
target_link_libraries(test_scaffolding PRIVATE colliscope_interface)
add_test(NAME TestScaffolding COMMAND test_scaffolding)

# Phase 1, Phase 2, Phase 3, Phase 4 & Phase 6 Catch2 Core, SVC-Hash, Baselines, Trace System, and Benchmark Engine test suite
add_executable(colliscope_tests
    cpp/test_main.cpp
    cpp/test_config.cpp
    cpp/test_metrics.cpp
    cpp/test_trace_parser.cpp
    cpp/test_svc_hash.cpp
    cpp/test_baselines.cpp
    cpp/test_trace_system.cpp
    cpp/test_benchmark_engine.cpp
)
target_include_directories(colliscope_tests PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
    ${CMAKE_SOURCE_DIR}/benchmarks
)
target_link_libraries(colliscope_tests PRIVATE
    colliscope_interface
    colliscope_svc_hash
    colliscope_chaining
    colliscope_cuckoo
    colliscope_hopscotch
    colliscope_benchmark_engine
)


add_test(NAME ColliScopeCoreTests COMMAND colliscope_tests)
