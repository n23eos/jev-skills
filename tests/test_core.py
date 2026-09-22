"""Offline regression tests for typed decisions and accounting."""

import math
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jev_skills.core import (Client, DecisionError, MODEL, NONE, build_request,
                             curl_transport, select, validate_input, validate_response)


def data(count=2):
    return {"request": "Choose a suitable fixture", "context": {"safe": True},
            "candidates": [{"id": f"item-{index}", "description": "Synthetic option"}
                           for index in range(count)]}


def response(payload, choice=None, confidence=0.9, usage=(11, 3)):
    options = list(payload["questions"]["selection"]["criteria"])
    choice = choice or options[0]
    probabilities = {option: 0.0 for option in options}
    probabilities[choice] = 1.0
    return {"model": MODEL, "answers": {"selection": {"type": "choice", "choice": choice,
            "confidence": confidence, "probabilities": probabilities}},
            "usage": {"input_tokens": usage[0], "output_tokens": usage[1]}}


class InputTests(unittest.TestCase):
    def test_reject_invalid_candidate_and_context(self):
        for changed in ({"id": NONE}, {"id": "bad key"}, {"id": "item-1"},
                        {"description": " "}):
            with self.subTest(changed=changed):
                sample = data()
                sample["candidates"][0].update(changed)
                with self.assertRaises(DecisionError):
                    validate_input(sample)
        sample = data()
        sample["context"] = {"bad": float("nan")}
        with self.assertRaises(DecisionError):
            validate_input(sample)

    def test_no_local_candidate_metadata_goes_to_request(self):
        sample = data()
        sample["candidates"][0]["path"] = "/private/secret"
        sample["candidates"][0]["size"] = "tiny"
        validated = validate_input(sample)
        payload = build_request("skill", validated, validated["candidates"])
        self.assertNotIn("/private/secret", repr(payload))
        self.assertNotIn("size", repr(payload))
        self.assertIn(NONE, payload["questions"]["selection"]["criteria"])

    def test_reject_unknown_model_size(self):
        sample = data()
        sample["candidates"][0]["size"] = "unlisted"
        with self.assertRaises(DecisionError):
            validate_input(sample)

    def test_group_limit_and_large_payload(self):
        validated = validate_input(data(255))
        with self.assertRaises(DecisionError):
            build_request("model", validated, validated["candidates"])
        sample = data(1)
        sample["request"] = "x" * 100_001
        with self.assertRaises(DecisionError):
            build_request("model", validate_input(sample), sample["candidates"])


class ResponseTests(unittest.TestCase):
    def setUp(self):
        sample = validate_input(data())
        self.payload = build_request("model", sample, sample["candidates"])
        self.options = set(self.payload["questions"]["selection"]["criteria"])

    def test_valid_response(self):
        answer = validate_response(response(self.payload), self.options)
        self.assertEqual(answer["selected"], "item-0")
        self.assertEqual(answer["usage"]["input_tokens"], 11)

    def test_reject_unknown_choice_bool_usage_and_bad_distribution(self):
        for mutation in (
            lambda raw: raw["answers"]["selection"].update(choice="missing"),
            lambda raw: raw["usage"].update(input_tokens=True),
            lambda raw: raw["answers"]["selection"].update(confidence=float("nan")),
            lambda raw: raw["answers"]["selection"].update(probabilities={"item-0": 1}),
            lambda raw: raw["answers"]["selection"].update(probabilities={key: 0.0 for key in self.options}),
        ):
            with self.subTest(mutation=mutation):
                raw = response(self.payload)
                mutation(raw)
                with self.assertRaises(DecisionError):
                    validate_response(raw, self.options)

    def test_huge_confidence_and_probability_are_typed_errors(self):
        huge = 10 ** 1000
        for field in ("confidence", "probability"):
            with self.subTest(field=field):
                raw = response(self.payload)
                if field == "confidence":
                    raw["answers"]["selection"]["confidence"] = huge
                else:
                    raw["answers"]["selection"]["probabilities"]["item-0"] = huge
                with self.assertRaises(DecisionError):
                    validate_response(raw, self.options)

    def test_huge_usage_is_rejected_before_cost_calculation(self):
        raw = response(self.payload, usage=(10 ** 1000, 3))
        with self.assertRaisesRegex(DecisionError, "invalid_usage"):
            validate_response(raw, self.options)


class SelectionTests(unittest.TestCase):
    def test_success_none_and_low_confidence(self):
        for choice, confidence, route, reason in (
            ("item-0", 0.9, "recommendation", None),
            (NONE, 0.9, "fallback", "none_selected"),
            ("item-0", 0.2, "fallback", "low_confidence"),
        ):
            with self.subTest(choice=choice, confidence=confidence):
                client = Client(lambda payload, timeout: response(payload, choice, confidence))
                result = select("model", data(), client)
                self.assertEqual((result["route"], result["reason"]), (route, reason))
                self.assertEqual((result["calls"], result["completed_calls"]), (1, 1))
                self.assertEqual(result["usage"], {"input_tokens": 11, "output_tokens": 3})

    def test_recommendation_reports_local_model_size(self):
        sample = data()
        sample["candidates"][0]["size"] = "tiny"
        result = select("model", sample, Client(lambda payload, timeout: response(payload)))
        self.assertEqual(result["model_size"], "tiny")

    def test_network_error_is_safe_and_accounted(self):
        def failed(payload, timeout):
            raise DecisionError("http_or_network_error")
        result = select("bug", data(), Client(failed))
        self.assertEqual(result["reason"], "http_or_network_error")
        self.assertEqual((result["calls"], result["completed_calls"], result["unaccounted_calls"]), (1, 0, 1))
        self.assertIsNone(result["estimated_known_cost_usd"])
        self.assertFalse(result["cost_complete"])

    def test_group_winners_and_final_call_all_accounted(self):
        seen = []
        def transport(payload, remaining):
            seen.append(remaining)
            return response(payload, usage=(7, 2))
        result = select("skill", data(255), Client(transport), batch_size=128)
        self.assertEqual((result["route"], result["selected"]), ("recommendation", "item-0"))
        self.assertEqual((result["calls"], result["completed_calls"], result["unaccounted_calls"]), (3, 3, 0))
        self.assertEqual(result["usage"], {"input_tokens": 21, "output_tokens": 6})
        self.assertEqual(len(result["judgments"]), 3)
        self.assertTrue(all(0 < remaining <= 3 for remaining in seen))

    def test_group_failure_retains_successful_call_usage(self):
        def transport(payload, remaining):
            options = payload["questions"]["selection"]["criteria"]
            if "item-128" in options:
                raise DecisionError("deadline_exceeded")
            return response(payload)
        result = select("skill", data(255), Client(transport), batch_size=128)
        self.assertEqual(result["reason"], "deadline_exceeded")
        self.assertEqual((result["calls"], result["completed_calls"], result["unaccounted_calls"]), (2, 1, 1))
        self.assertEqual(result["usage"], {"input_tokens": 11, "output_tokens": 3})
        self.assertFalse(result["cost_complete"])

    def test_group_low_confidence_stops_before_final_round(self):
        def transport(payload, remaining):
            options = payload["questions"]["selection"]["criteria"]
            confidence = 0.599 if "item-2" in options else 0.9
            return response(payload, confidence=confidence)
        result = select("skill", data(3), Client(transport), batch_size=2, threshold=0.6)
        self.assertEqual((result["route"], result["reason"]), ("fallback", "low_confidence"))
        self.assertEqual(result["confidence"], 0.599)
        self.assertEqual((result["calls"], result["completed_calls"]), (2, 2))
        self.assertEqual(len(result["judgments"]), 2)

    def test_threshold_is_inclusive_at_exact_boundary(self):
        for confidence, expected in ((0.6, "recommendation"), (0.599, "fallback")):
            with self.subTest(confidence=confidence):
                result = select("model", data(), Client(lambda payload, remaining: response(payload, confidence=confidence)),
                                threshold=0.6)
                self.assertEqual(result["route"], expected)

    def test_huge_response_usage_falls_back_without_cost_overflow(self):
        result = select("model", data(), Client(lambda payload, remaining: response(payload, usage=(10 ** 1000, 3))))
        self.assertEqual((result["route"], result["reason"]), ("fallback", "invalid_usage"))
        self.assertEqual((result["calls"], result["completed_calls"], result["unaccounted_calls"]), (1, 0, 1))
        self.assertIsNone(result["estimated_known_cost_usd"])

    def test_timeout_and_threshold_are_bounded(self):
        seen = []
        result = select("tests", data(), Client(lambda payload, timeout: (seen.append(timeout), response(payload))[1]), timeout=0.05)
        self.assertEqual(result["route"], "recommendation")
        self.assertLessEqual(seen[0], 0.05)
        for wrong in (0, math.inf, float("nan"), True, 61):
            with self.subTest(wrong=wrong), self.assertRaises(DecisionError):
                select("tests", data(), Client(), timeout=wrong)


class TransportTests(unittest.TestCase):
    def test_subprocess_timeout_is_sanitized_and_never_retried(self):
        sample = validate_input(data())
        payload = build_request("model", sample, sample["candidates"])
        timeout = subprocess.TimeoutExpired("curl", 0.5, output="PRIVATE_RESPONSE", stderr="PRIVATE_ERROR")
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "PRIVATE_KEY"}), \
                patch("jev_skills.core.subprocess.run", side_effect=timeout) as run:
            with self.assertRaises(DecisionError) as caught:
                curl_transport(payload, 0.5)
        self.assertEqual(str(caught.exception), "deadline_exceeded")
        self.assertNotIn("PRIVATE", str(caught.exception))
        run.assert_called_once()

    def test_failed_http_does_not_expose_key_or_response_body(self):
        sample = validate_input(data())
        payload = build_request("model", sample, sample["candidates"])
        fake = type("Result", (), {"returncode": 22, "stdout": "PRIVATE_RESPONSE", "stderr": "PRIVATE_ERROR"})()
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "PRIVATE_KEY"}), \
                patch("jev_skills.core.subprocess.run", return_value=fake) as run:
            with self.assertRaises(DecisionError) as caught:
                curl_transport(payload, 0.5)
        self.assertEqual(str(caught.exception), "http_or_network_error")
        self.assertNotIn("PRIVATE_KEY", repr(run.call_args.args))
        self.assertIn("--max-time", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 0.6)

    def test_missing_key_never_starts_transport(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}), \
                patch("jev_skills.core.subprocess.run", side_effect=AssertionError("network")):
            with self.assertRaisesRegex(DecisionError, "missing_or_invalid_api_key"):
                curl_transport({}, 0.5)


if __name__ == "__main__":
    unittest.main()
