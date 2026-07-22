#!/usr/bin/env python3
"""Tests for natural-language description prompt construction."""

from __future__ import annotations

import unittest

from dataset.generate_nl_description import (
    build_signature_prompt_section,
    extract_spectra_signature,
    generation_variant_name,
    render_prompt,
)


class GenerateNlDescriptionTests(unittest.TestCase):
    def test_extract_spectra_signature_preserves_names_and_types(self) -> None:
        signature = extract_spectra_signature(
            """
            module Rover
            type Mode = {SEEK, MEASURE, IDLE};
            env boolean gravityDetected; // sensor input
            env Int(0..7) level;
            sys Mode mode;
            sys {LEFT, RIGHT} turn;
            """
        )

        self.assertEqual(signature["spec_name"], "Rover")
        self.assertEqual(signature["type_definitions"], [{"name": "Mode", "domain": "{SEEK, MEASURE, IDLE}"}])
        self.assertEqual(
            signature["environment"],
            [
                {"name": "gravityDetected", "type": "boolean"},
                {"name": "level", "type": "Int(0..7)"},
            ],
        )
        self.assertEqual(
            signature["system"],
            [
                {"name": "mode", "type": "Mode"},
                {"name": "turn", "type": "{LEFT, RIGHT}"},
            ],
        )

    def test_signature_prompt_section_requests_fixed_interface(self) -> None:
        section = build_signature_prompt_section(
            {
                "spec_name": "Minepump",
                "type_definitions": [],
                "environment": [{"name": "highwater", "type": "boolean"}],
                "system": [{"name": "pump", "type": "boolean"}],
            }
        )

        self.assertIn("Additional fixed-interface requirement:", section)
        self.assertIn("- highwater: boolean", section)
        self.assertIn("- pump: boolean", section)
        self.assertIn("Do not rename variables", section)

    def test_render_prompt_appends_signature_section(self) -> None:
        rendered = render_prompt("Translate {spectra_code}", "spec Foo", "Environment variables:\n- request: boolean")

        self.assertIn("Translate spec Foo", rendered)
        self.assertTrue(rendered.endswith("Environment variables:\n- request: boolean\n"))

    def test_generation_variant_name_includes_signature_tag(self) -> None:
        variant = generation_variant_name(
            model="llama-3.3-70b-instruct",
            prompt_name="spectra_to_english_v1",
            temperature=None,
            top_p=None,
            max_tokens=None,
            generation_config_key="abcdef1234567890",
            filename_tag="sig",
        )

        self.assertIn("tag=sig", variant)
        self.assertTrue(variant.endswith("id=abcdef123456"))


if __name__ == "__main__":
    unittest.main()
