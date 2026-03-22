---
name: duck
description: "Review code files and directories with relentless questioning to identify design issues early. Use this skill when starting on a new feature, onboarding to a codebase, or auditing existing code. The goal is to uncover potential design problems, edge cases, and ambiguities before implementation begins by asking thorough questions about the code's structure, dependencies, and behavior."
argument-hint: "Provide file paths or directories to review, along with any specific areas of concern or focus."
---


Review all of the files provided. If a directory is provided, review all files within the directory, and question me relentlessly using #askQuestions about them along with suggested answers, so that we can cut off any design issues now

You should ask me many questions in one pass and then update the plans based on my answers

You should always update the plans after each round of questions. If there are open questions from this round, include them in the updates to the plans in an "Open Questions" section and then ask me about them in the next round

Delegate updating plans to a #runSubagent to keep your context clean

You should perform AT LEAST 3 rounds of questioning but continue until we have covered the holes.

While asking me questions, I might tell you to research things. You should always research those things using another subagent before making updates to plans. Any research you do should be included in the updates to the plans so that we have a record of it. You should also include any relevant information you find in the research in the updates to the plans, even if it doesn't directly answer one of your questions, as it might be useful later on. Be sure to include the links to any files you read in the research in the updates to the plans as well so that we have a record of what you read and can refer back to it later if needed.
