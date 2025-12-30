cmake_minimum_required(VERSION 3.16)
project(raft_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Sanitizer options
option(ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ENABLE_TSAN "Enable ThreadSanitizer" OFF)
option(ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)
option(ENABLE_MSAN "Enable MemorySanitizer" OFF)
option(ENABLE_COVERAGE "Enable code coverage" OFF)
option(BUILD_TESTS "Build unit and integration tests" OFF)

# Sanitizer flags
if(ENABLE_ASAN)
    message(STATUS "AddressSanitizer enabled")
    set(SANITIZER_FLAGS "-fsanitize=address -fno-omit-frame-pointer -g")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${SANITIZER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SANITIZER_FLAGS}")
endif()

if(ENABLE_TSAN)
    message(STATUS "ThreadSanitizer enabled")
    set(SANITIZER_FLAGS "-fsanitize=thread -g")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${SANITIZER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SANITIZER_FLAGS}")
endif()

if(ENABLE_UBSAN)
    message(STATUS "UndefinedBehaviorSanitizer enabled")
    set(SANITIZER_FLAGS "-fsanitize=undefined -fno-omit-frame-pointer -g")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${SANITIZER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SANITIZER_FLAGS}")
endif()

if(ENABLE_MSAN)
    message(STATUS "MemorySanitizer enabled")
    set(SANITIZER_FLAGS "-fsanitize=memory -fno-omit-frame-pointer -g")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${SANITIZER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${SANITIZER_FLAGS}")
endif()

if(ENABLE_COVERAGE)
    message(STATUS "Code coverage enabled")
    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --coverage -fprofile-arcs -ftest-coverage")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} --coverage")
endif()

# Compiler warnings
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -Wextra -Wpedantic")

# Find required packages
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# Find Abseil (required by newer protobuf versions)
find_package(absl CONFIG QUIET)
if(absl_FOUND)
    message(STATUS "Found Abseil via CMake config")
else()
    # Try pkg-config as fallback
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(ABSL QUIET absl_base absl_log absl_log_internal_check_op)
    endif()
endif()

# Find the gRPC C++ plugin
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin)

# Proto file
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../proto/raft.proto")

# Generate protobuf and gRPC sources
set(PROTO_SRCS "${CMAKE_CURRENT_BINARY_DIR}/raft.pb.cc")
set(PROTO_HDRS "${CMAKE_CURRENT_BINARY_DIR}/raft.pb.h")
set(GRPC_SRCS "${CMAKE_CURRENT_BINARY_DIR}/raft.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_CURRENT_BINARY_DIR}/raft.grpc.pb.h")

add_custom_command(
    OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND protobuf::protoc
    ARGS --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
         --cpp_out "${CMAKE_CURRENT_BINARY_DIR}"
         -I "${CMAKE_CURRENT_SOURCE_DIR}/../proto"
         --plugin=protoc-gen-grpc="${GRPC_CPP_PLUGIN}"
         "${PROTO_FILE}"
    DEPENDS "${PROTO_FILE}"
)

# Include generated headers
include_directories("${CMAKE_CURRENT_BINARY_DIR}")

# Build the server executable
add_executable(server
    server.cpp
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

# Link libraries
target_link_libraries(server
    gRPC::grpc++
    gRPC::grpc++_reflection
    protobuf::libprotobuf
    Threads::Threads
)

# Link Abseil libraries if found (required for newer protobuf)
if(absl_FOUND)
    target_link_libraries(server
        absl::base
        absl::log
        absl::log_internal_check_op
        absl::log_internal_message
        absl::status
        absl::statusor
        absl::strings
        absl::synchronization
        absl::time
    )
elseif(ABSL_FOUND)
    target_link_libraries(server ${ABSL_LIBRARIES})
    target_include_directories(server PRIVATE ${ABSL_INCLUDE_DIRS})
endif()

# Install
install(TARGETS server DESTINATION bin)

# Testing
if(BUILD_TESTS)
    enable_testing()

    # Find GTest
    find_package(GTest CONFIG QUIET)
    if(NOT GTest_FOUND)
        include(FetchContent)
        FetchContent_Declare(
            googletest
            GIT_REPOSITORY https://github.com/google/googletest.git
            GIT_TAG v1.14.0
        )
        FetchContent_MakeAvailable(googletest)
    endif()

    # Create a library for the Raft implementation (for testing)
    add_library(raft_lib STATIC
        ${PROTO_SRCS}
        ${GRPC_SRCS}
    )
    target_include_directories(raft_lib PUBLIC "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")
    target_link_libraries(raft_lib
        gRPC::grpc++
        gRPC::grpc++_reflection
        protobuf::libprotobuf
        Threads::Threads
    )
    if(absl_FOUND)
        target_link_libraries(raft_lib
            absl::base
            absl::log
            absl::log_internal_check_op
            absl::log_internal_message
            absl::status
            absl::statusor
            absl::strings
            absl::synchronization
            absl::time
        )
    endif()

    # Unit tests
    add_executable(raft_unit_tests
        tests/unit_tests.cpp
        ${PROTO_SRCS}
        ${GRPC_SRCS}
    )
    target_include_directories(raft_unit_tests PRIVATE "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")
    target_link_libraries(raft_unit_tests
        GTest::gtest
        GTest::gtest_main
        GTest::gmock
        gRPC::grpc++
        gRPC::grpc++_reflection
        protobuf::libprotobuf
        Threads::Threads
    )
    if(absl_FOUND)
        target_link_libraries(raft_unit_tests
            absl::base
            absl::log
            absl::log_internal_check_op
            absl::log_internal_message
            absl::status
            absl::statusor
            absl::strings
            absl::synchronization
            absl::time
        )
    endif()

    # Integration tests
    add_executable(raft_integration_tests
        tests/integration_tests.cpp
        ${PROTO_SRCS}
        ${GRPC_SRCS}
    )
    target_include_directories(raft_integration_tests PRIVATE "${CMAKE_CURRENT_BINARY_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}")
    target_link_libraries(raft_integration_tests
        GTest::gtest
        GTest::gtest_main
        GTest::gmock
        gRPC::grpc++
        gRPC::grpc++_reflection
        protobuf::libprotobuf
        Threads::Threads
    )
    if(absl_FOUND)
        target_link_libraries(raft_integration_tests
            absl::base
            absl::log
            absl::log_internal_check_op
            absl::log_internal_message
            absl::status
            absl::statusor
            absl::strings
            absl::synchronization
            absl::time
        )
    endif()

    add_test(NAME unit_tests COMMAND raft_unit_tests)
    add_test(NAME integration_tests COMMAND raft_integration_tests)
endif()
