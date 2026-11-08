//! B-25: every text of the window has a German translation.

#![allow(clippy::unwrap_used)]

use std::fs;

/// The quoted strings after `marker` in `text`.
fn quoted_after<'a>(text: &'a str, marker: &str) -> Vec<&'a str> {
    text.split(marker)
        .skip(1)
        .map(|rest| rest.split('"').next().unwrap())
        .collect()
}

#[test]
fn every_text_has_a_german_translation() {
    let slint = fs::read_to_string("ui/control.slint").unwrap();
    let po = fs::read_to_string("translations/de/LC_MESSAGES/electrip-ui.po").unwrap();
    let texts = quoted_after(&slint, "@tr(\"");
    let translated = quoted_after(&po, "msgid \"");
    assert!(!texts.is_empty());
    for text in texts {
        assert!(translated.contains(&text), "ERROR no German for {text:?}");
    }
    // The first entry is the header.
    for translation in quoted_after(&po, "msgstr \"").iter().skip(1) {
        assert!(!translation.is_empty());
    }
}
