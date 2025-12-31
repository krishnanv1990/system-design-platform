cmake_minimum_required(VERSION 3.14)
project(tpc_server)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)

set(PROTO_FILE ${CMAKE_CURRENT_SOURCE_DIR}/../../proto/two_phase_commit.proto)
get_filename_component(PROTO_PATH "${PROTO_FILE}" DIRECTORY)

set(PROTO_SRCS "${CMAKE_CURRENT_BINARY_DIR}/two_phase_commit.pb.cc")
set(PROTO_HDRS "${CMAKE_CURRENT_BINARY_DIR}/two_phase_commit.pb.h")
set(GRPC_SRCS "${CMAKE_CURRENT_BINARY_DIR}/two_phase_commit.grpc.pb.cc")
set(GRPC_HDRS "${CMAKE_CURRENT_BINARY_DIR}/two_phase_commit.grpc.pb.h")

find_program(_PROTOBUF_PROTOC protoc)
find_program(_GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)

add_custom_command(
    OUTPUT "${PROTO_SRCS}" "${PROTO_HDRS}" "${GRPC_SRCS}" "${GRPC_HDRS}"
    COMMAND ${_PROTOBUF_PROTOC}
    ARGS --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
         --cpp_out "${CMAKE_CURRENT_BINARY_DIR}"
         -I "${PROTO_PATH}"
         --plugin=protoc-gen-grpc="${_GRPC_CPP_PLUGIN_EXECUTABLE}"
         "${PROTO_FILE}"
    DEPENDS "${PROTO_FILE}"
)

include_directories("${CMAKE_CURRENT_BINARY_DIR}")

add_executable(server server.cpp ${PROTO_SRCS} ${GRPC_SRCS})
target_link_libraries(server gRPC::grpc++ protobuf::libprotobuf)
