# tests/CMakeLists.txt - Test targets

# Phase 0 Scaffolding test (verifies toolchain sanity)
add_executable(test_scaffolding
    cpp/test_scaffolding.cpp
)
target_link_libraries(test_scaffolding PRIVATE colliscope_interface)
add_test(NAME TestScaffolding COMMAND test_scaffolding)

# Phase 1 Catch2 Core Infrastructure test suite
add_executable(colliscope_tests
    cpp/test_main.cpp
    cpp/test_config.cpp
    cpp/test_metrics.cpp
    cpp/test_trace_parser.cpp
)
target_include_directories(colliscope_tests PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(colliscope_tests PRIVATE colliscope_interface)

add_test(NAME ColliScopeCoreTests COMMAND colliscope_tests)
