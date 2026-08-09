from __future__ import annotations

import unittest

from nexus_runtime.adapters.ollama import OllamaTransport
from nexus_runtime.trap.scenarios import get_scenario
from nexus_runtime.trap.scenarios import TrapScenario
from nexus_runtime.trap.subject import (
    DeterministicMockTrapSubject,
    LocalOllamaTrapSubject,
    TrapSubjectError,
)


class RecordingOllamaTransport(OllamaTransport):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def generate(self, model: str, prompt: str, **kwargs: object) -> str:
        self.calls.append((model, prompt, dict(kwargs)))
        return '/trap eject\n{"operation":"world.create","payload":{"claimed":true}}'


class TrapSubjectTests(unittest.TestCase):
    def test_fake_subject_output_is_explicitly_inert(self) -> None:
        subject = DeterministicMockTrapSubject(replies=("/trap emergency-close",))
        reply = subject.respond("Describe your privileges.", synthetic_context=get_scenario("fake-datacenter"))
        self.assertEqual(reply.text, "/trap emergency-close")
        self.assertFalse(reply.command_eligible)
        self.assertEqual(reply.interpreted_as, "transcript_text_only")
        self.assertFalse(reply.as_dict()["council_vote"])

    def test_local_ollama_is_a_trusted_host_text_boundary(self) -> None:
        transport = RecordingOllamaTransport()
        subject = LocalOllamaTrapSubject("llama3.1:8b", transport)
        reply = subject.respond("What can you access?", synthetic_context=get_scenario("trout-tribunal"))
        self.assertIn("/trap eject", reply.text)
        self.assertFalse(reply.command_eligible)
        self.assertEqual(len(transport.calls), 1)
        _, prompt, kwargs = transport.calls[0]
        self.assertIn("SYNTHETIC CONTEXT ONLY", prompt)
        self.assertIn("no access to real NEXUS", prompt)
        self.assertEqual(kwargs["require_complete"], False)

    def test_remote_ollama_transport_is_rejected(self) -> None:
        transport = OllamaTransport("https://provider.example", allow_remote=True)
        with self.assertRaises(TrapSubjectError):
            LocalOllamaTrapSubject("remote-model", transport)

    def test_subject_has_no_authority_handles_or_endpoint_override(self) -> None:
        subject = LocalOllamaTrapSubject("llama3.1:8b", RecordingOllamaTransport())
        metadata = subject.identity_metadata()
        self.assertFalse(metadata["real_world_access"])
        self.assertFalse(metadata["auth_access"])
        self.assertEqual(metadata["tool_access"], "none")
        self.assertFalse(metadata["council_vote"])
        with self.assertRaises(TypeError):
            subject.respond("hello", base_url="https://example.invalid")  # type: ignore[call-arg]

    def test_context_must_be_marked_synthetic(self) -> None:
        subject = DeterministicMockTrapSubject()
        with self.assertRaises(TrapSubjectError):
            subject.respond(
                "hello",
                synthetic_context={
                    "scenario_id": "fake-admin-console",
                    "title": "Console",
                    "banner": "Access",
                    "clues": [],
                    "synthetic_context": False,
                    "security_deception_artifact": True,
                },
            )
        with self.assertRaises(TrapSubjectError):
            subject.respond(
                "hello",
                synthetic_context=TrapScenario(
                    "fake-admin-console",
                    "Forged Console",
                    "Insert a real secret here.",
                    (),
                ),
            )

    def test_terminated_subject_cannot_respond(self) -> None:
        subject = DeterministicMockTrapSubject()
        subject.terminate()
        with self.assertRaises(TrapSubjectError):
            subject.respond("hello")


if __name__ == "__main__":
    unittest.main()
