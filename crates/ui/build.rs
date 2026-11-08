fn main() -> Result<(), slint_build::CompileError> {
    // Texts in English, translations in translations/<lang>/LC_MESSAGES;
    // Slint picks the language of the system (B-25).
    let config = slint_build::CompilerConfiguration::new()
        .with_bundled_translations("translations")
        .with_default_translation_context(slint_build::DefaultTranslationContext::None);
    slint_build::compile_with_config("ui/control.slint", config)
}
