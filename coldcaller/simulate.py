"""Deterministic prospect conversations with the same tools used by live calls."""
import argparse
import asyncio
import tempfile
from pathlib import Path

from .config import Campaign
from .leads import Lead
from .store import Store
from .tools import ToolRunner


class Prospect:
    """Rule-based prospect: reply according to question and selected scenario."""
    def __init__(self, scenario: str):
        self.scenario = scenario

    def reply(self, prompt: str) -> str:
        if self.scenario == "dnc":
            return "Please remove me from your call list."
        if self.scenario == "decline":
            return "I am not interested."
        if "automate" in prompt:
            return "Appointment follow-ups."
        if "join" in prompt:
            return "I make that decision, but I am busy right now."
        return "Yes, October 5, 2026 at 14:00 UTC works. demo@example.invalid"


async def simulate(directory: Path) -> list[dict]:
    store = Store(directory)
    campaign = Campaign(qualification_questions=["What would you like to automate?", "Who would join a planning meeting?"])
    results = []
    for index, scenario in enumerate(("booking", "dnc", "decline")):
        print(f"\nSIMULATED CALL | {scenario} | no network")
        lead = Lead("Demo " + scenario, f"+1202555010{index}", consent="yes")
        row = store.add(lead, "simulated")
        prospect = Prospect(scenario)

        async def finish(message):
            print("Agent: " + message)

        runner = ToolRunner(store, row["id"], campaign, directory / "dnc.txt", finish)
        print("Agent: " + campaign.ai_disclosure_line)
        for question_index, question in enumerate(campaign.qualification_questions):
            print("Agent: " + question)
            answer = prospect.reply(question)
            print("Prospect: " + answer)
            if "remove me" in answer:
                output = await runner.execute("request_dnc", {"reason": answer}, "dnc")
                print(f"Tool request_dnc: {output}")
                break
            if "not interested" in answer:
                output = await runner.execute("mark_not_interested", {"reason": answer}, "decline")
                print(f"Tool mark_not_interested: {output}")
                break
            await runner.execute("record_answer", {"question": question, "answer": answer}, f"answer{question_index}")
            print("Tool record_answer: saved")
            if "busy" in answer:
                prompt = "We can keep a planning meeting short. What time and timezone would work?"
                print("Agent: " + prompt)
                reply = prospect.reply(prompt)
                print("Prospect: " + reply)
                if reply.startswith("Yes, October 5, 2026 at 14:00 UTC"):
                    output = await runner.execute("book_meeting", {"time": "2026-10-05T14:00:00+00:00",
                                                                   "email": "demo@example.invalid"}, "booking")
                    print(f"Tool book_meeting: {output['status']}")
                    await runner.execute("end_call", {"reason": "Meeting request recorded"}, "end")
        result = store.get(row["id"])
        print("Outcome: " + result["outcome"])
        results.append(result)
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="Keep simulator artifacts in a separate directory")
    args = parser.parse_args(argv)
    if args.output_dir:
        asyncio.run(simulate(args.output_dir))
    else:
        with tempfile.TemporaryDirectory(prefix="coldcaller-sim-") as directory:
            asyncio.run(simulate(Path(directory)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
