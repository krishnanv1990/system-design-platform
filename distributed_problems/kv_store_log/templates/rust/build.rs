fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("../../proto/kv_store_log.proto")?;
    Ok(())
}
