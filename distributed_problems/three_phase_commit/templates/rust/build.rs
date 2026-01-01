fn main() -> Result<(), Box<dyn std::error::Error>> {
    tonic_build::compile_protos("../../proto/three_phase_commit.proto")?;
    Ok(())
}
