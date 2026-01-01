cmake_minimum_required(VERSION 3.16)
project(sliding_window_log_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Sanitizer options
option(ENABLE_ASAN "Enable AddressSanitizer" OFF)
option(ENABLE_TSAN "Enable ThreadSanitizer" OFF)
option(ENABLE_UBSAN "Enable UndefinedBehaviorSanitizer" OFF)

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
    find_package(PkgConfig QUIET)
    if(PkgConfig_FOUND)
        pkg_check_modules(ABSL QUIET absl_base absl_log absl_log_internal_check_op)
    endif()
endif()

# Find the gRPC C++ plugin
find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin)

# Proto file - note the path goes up to proto directory
set(PROTO_FILE "${CMAKE_CURRENT_SOURCE_DIR}/../../proto/sliding_window_log.proto")

# Generate protobuf and gRPC sources
set(PROTO_SRCS "${CMAKE_CURRENT_BINARY_DIR}/sliding_window_log.pb.cc")
set(PROTO_HDRS "${CMAKE_CURRENT_BINARY_DIR}/sliding_window_log.pb.h")
set(GRPC_SRCS "${CMAKE_CURRENT_BINARY_DIR}/sliding_window_log.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_CURRENT_BINARY_DIR}/sliding_window_log.grpc.pb.h")

add_custom_command(
    OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND protobuf::protoc
    ARGS --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
         --cpp_out "${CMAKE_CURRENT_BINARY_DIR}"
         -I "${CMAKE_CURRENT_SOURCE_DIR}/../../proto"
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

# Link Abseil libraries if found
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
