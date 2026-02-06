on join_lines(line_list)
	set old_delims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to return
	set joined_text to line_list as text
	set AppleScript's text item delimiters to old_delims
	return joined_text
end join_lines

on set_title_and_body(target_slide, slide_title, body_lines)
	tell application "Keynote"
		tell target_slide
			try
				set object text of default title item to slide_title
			end try
			if (count of body_lines) > 0 then
				try
					set object text of default body item to my join_lines(body_lines)
				end try
			end if
		end tell
	end tell
end set_title_and_body

on add_bullet_slide(doc_ref, layout_name, slide_title, body_lines)
	tell application "Keynote"
		tell doc_ref
			set new_slide to make new slide with properties {base layout:slide layout layout_name}
		end tell
	end tell
	my set_title_and_body(new_slide, slide_title, body_lines)
	return new_slide
end add_bullet_slide

on add_chart_slide(doc_ref, slide_title, caption_text, row_names, column_names, chart_data, chart_kind, group_kind)
	tell application "Keynote"
		tell doc_ref
			set new_slide to make new slide with properties {base layout:slide layout "Blank"}
			tell new_slide
				set title_box to make new text item with properties {object text:slide_title, position:{60, 30}, width:900, height:60}
				set caption_box to make new text item with properties {object text:caption_text, position:{60, 88}, width:900, height:45}
				set the_chart to add chart new_slide row names row_names column names column_names data chart_data type chart_kind group by group_kind
				set position of last chart to {90, 150}
				set width of last chart to 840
				set height of last chart to 430
			end tell
		end tell
	end tell
end add_chart_slide

tell application "Keynote"
	activate

	set output_key to POSIX file "/Users/thristannewman/ADinsights/docs/project/adinsights-stakeholder-deck.key"
	set output_pptx to POSIX file "/Users/thristannewman/ADinsights/docs/project/adinsights-stakeholder-deck.pptx"

	set deck to make new document with properties {document theme:theme "White"}
	tell deck
		set object text of default title item of first slide to "ADinsights"
		set object text of default body item of first slide to "Stakeholder Briefing: Why this app matters and how it drives decisions"
	end tell

	my add_bullet_slide(deck, "Title & Bullets", "The Problem We Solve", {"Campaign data is fragmented across Meta and Google interfaces", "Teams spend hours reconciling exports before every client review", "Leaders get delayed performance visibility", "Ops teams often detect stale data after it impacts reporting"})

	my add_bullet_slide(deck, "Title & Bullets", "Who Needs This", {"Agency leadership: portfolio visibility and growth confidence", "Account and client success leads: faster weekly and monthly reporting", "Analysts and media buyers: optimization-ready drill-downs", "Finance and revenue ops: standardized spend and outcome views", "Ops, security, and engineering: reliable, tenant-safe delivery"})

	my add_bullet_slide(deck, "Title & Bullets", "How ADinsights Works", {"Airbyte ingests source platform metrics on schedule", "dbt normalizes staging and mart models with shared metric definitions", "Django API serves tenant-scoped aggregated snapshots", "React dashboards present KPI cards, trends, tables, and geo maps", "Health checks and telemetry expose freshness and sync status"})

	my add_chart_slide(deck, "Capability Maturity Snapshot", "Current capability areas in ADinsights", {"Capability Areas"}, {"Built", "In Progress", "Planned"}, {{6, 2, 4}}, pie_2d, chart row)

	my add_chart_slide(deck, "Operational Reliability Targets", "SLA and freshness targets aligned to stakeholder reporting needs", {"Target"}, {"Nightly Sync", "dbt Freshness", "Dashboard Freshness"}, {{99, 98, 99}}, vertical_bar_2d, chart row)

	my add_chart_slide(deck, "Stakeholder Value Impact", "Illustrative value score by role (higher is better)", {"Leadership", "Account Leads", "Analysts", "Finance", "Ops"}, {"Value Score"}, {{90}, {88}, {92}, {80}, {86}}, horizontal_bar_2d, chart row)

	my add_chart_slide(deck, "90-Day Adoption Path", "Target tenant coverage after rollout kickoff", {"Tenant Coverage"}, {"Day 30", "Day 60", "Day 90"}, {{20, 55, 90}}, line_2d, chart row)

	my add_bullet_slide(deck, "Title & Bullets", "Security and Governance", {"Aggregated advertising metrics only (no user-level PII)", "Per-tenant secret encryption with AES-GCM and KMS-backed key strategy", "Tenant isolation guardrails enforced across ingestion, API, and UI", "Structured telemetry for incident triage and auditability"})

	my add_bullet_slide(deck, "Title & Bullets", "Risk Management", {"Data quality regression risk: dbt tests plus checklist-based validation", "Snapshot staleness risk: freshness alerts and runbook response", "Connector coverage risk: phased roadmap for additional platforms", "Secrets exposure risk: encryption, log scrubbing, and access controls"})

	my add_bullet_slide(deck, "Title & Bullets", "Recommended Demo Flow", {"1) Leadership view: KPI and pacing overview", "2) Account lead view: tenant switch and report posture", "3) Analyst view: filters, trends, campaign and creative drill-down", "4) Ops view: freshness indicator and sync telemetry", "5) Security view: tenant and encryption controls"})

	my add_bullet_slide(deck, "Title & Bullets", "Decision Asks", {"Approve pilot tenant list and baseline success metrics", "Confirm weekly operating cadence across leadership, account, and analyst roles", "Assign owners for reliability escalation and stakeholder communications", "Prioritize next-wave scope: connector expansion and advanced reporting"})

	export deck to output_pptx as Microsoft PowerPoint
	save deck in output_key
	close deck saving no
end tell
