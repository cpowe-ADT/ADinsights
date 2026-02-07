on join_lines(line_list)
	set old_delims to AppleScript's text item delimiters
	set AppleScript's text item delimiters to return
	set joined_text to line_list as text
	set AppleScript's text item delimiters to old_delims
	return joined_text
end join_lines

on bulletize_lines(line_list)
	set out_lines to {}
	repeat with one_line in line_list
		set end of out_lines to "- " & (one_line as text)
	end repeat
	return my join_lines(out_lines)
end bulletize_lines

on style_title_text(text_item_ref)
	tell application "Keynote"
		set font of object text of text_item_ref to "Calibri"
		set size of object text of text_item_ref to 40
		set color of object text of text_item_ref to {65535, 65535, 65535}
	end tell
end style_title_text

on style_body_text(text_item_ref, pt_size)
	tell application "Keynote"
		set font of object text of text_item_ref to "Arial"
		set size of object text of text_item_ref to pt_size
		set color of object text of text_item_ref to {0, 0, 0}
	end tell
end style_body_text

on add_header_block(target_slide, slide_title)
	tell application "Keynote"
		tell target_slide
			make new image with properties {file:POSIX file "/Users/thristannewman/ADinsights/docs/project/assets/header_bar.png", position:{0, 0}, width:1024, height:140}
			set title_box to make new text item with properties {object text:slide_title, position:{54, 34}, width:920, height:74}
		end tell
	end tell
	my style_title_text(title_box)
end add_header_block

on add_title_slide(doc_ref)
	tell application "Keynote"
		tell doc_ref
			set s to first slide
			set base layout of s to slide layout "Blank"
		end tell
	end tell
	my add_header_block(s, "ADtelligent - ADinsights Stakeholder Brief")
	tell application "Keynote"
		tell s
			set subtitle_box to make new text item with properties {object text:"Unified paid-media intelligence for faster, safer stakeholder decisions", position:{70, 220}, width:880, height:120}
			set sub2_box to make new text item with properties {object text:"Theme: Orange + White titles, Black body text | Audience: Leadership, Account, Analyst, Ops, Security", position:{70, 330}, width:880, height:90}
		end tell
	end tell
	my style_body_text(subtitle_box, 34)
	my style_body_text(sub2_box, 21)
end add_title_slide

on add_bullet_slide(doc_ref, slide_title, body_lines)
	tell application "Keynote"
		tell doc_ref
			set s to make new slide with properties {base layout:slide layout "Blank"}
		end tell
	end tell
	my add_header_block(s, slide_title)
	tell application "Keynote"
		tell s
			set body_box to make new text item with properties {object text:my bulletize_lines(body_lines), position:{70, 178}, width:884, height:520}
		end tell
	end tell
	my style_body_text(body_box, 25)
	return s
end add_bullet_slide

on add_two_column_slide(doc_ref, slide_title, left_heading, left_lines, right_heading, right_lines)
	tell application "Keynote"
		tell doc_ref
			set s to make new slide with properties {base layout:slide layout "Blank"}
		end tell
	end tell
	my add_header_block(s, slide_title)
	tell application "Keynote"
		tell s
			set left_head to make new text item with properties {object text:left_heading, position:{70, 172}, width:420, height:44}
			set right_head to make new text item with properties {object text:right_heading, position:{536, 172}, width:420, height:44}
			set left_body to make new text item with properties {object text:my bulletize_lines(left_lines), position:{70, 214}, width:420, height:470}
			set right_body to make new text item with properties {object text:my bulletize_lines(right_lines), position:{536, 214}, width:420, height:470}
		end tell
	end tell
	my style_body_text(left_head, 24)
	my style_body_text(right_head, 24)
	my style_body_text(left_body, 20)
	my style_body_text(right_body, 20)
	return s
end add_two_column_slide

on add_flow_graphic_slide(doc_ref, slide_title, caption_text)
	tell application "Keynote"
		tell doc_ref
			set s to make new slide with properties {base layout:slide layout "Blank"}
		end tell
	end tell
	my add_header_block(s, slide_title)
	tell application "Keynote"
		tell s
			set cap_box to make new text item with properties {object text:caption_text, position:{70, 154}, width:884, height:44}
			set b1 to make new shape with properties {position:{60, 280}, width:190, height:90}
			set b2 to make new shape with properties {position:{290, 280}, width:190, height:90}
			set b3 to make new shape with properties {position:{520, 280}, width:190, height:90}
			set b4 to make new shape with properties {position:{750, 280}, width:190, height:90}
			set object text of b1 to "Airbyte\nIngestion"
			set object text of b2 to "dbt\nModeling"
			set object text of b3 to "Django API\nSnapshots"
			set object text of b4 to "React UI\nDashboards"
			set a1 to make new text item with properties {object text:"->", position:{255, 300}, width:30, height:50}
			set a2 to make new text item with properties {object text:"->", position:{485, 300}, width:30, height:50}
			set a3 to make new text item with properties {object text:"->", position:{715, 300}, width:30, height:50}
			set note_box to make new text item with properties {object text:"Tenant-safe context across every layer | Aggregated metrics only | Freshness monitored", position:{70, 430}, width:884, height:80}
		end tell
	end tell
	my style_body_text(cap_box, 18)
	my style_body_text(b1, 16)
	my style_body_text(b2, 16)
	my style_body_text(b3, 16)
	my style_body_text(b4, 16)
	my style_body_text(a1, 34)
	my style_body_text(a2, 34)
	my style_body_text(a3, 34)
	my style_body_text(note_box, 20)
	return s
end add_flow_graphic_slide

on add_chart_slide(doc_ref, slide_title, caption_text, row_names, column_names, chart_data, chart_kind)
	tell application "Keynote"
		tell doc_ref
			set s to make new slide with properties {base layout:slide layout "Blank"}
		end tell
	end tell
	my add_header_block(s, slide_title)
	tell application "Keynote"
		tell s
			set cap_box to make new text item with properties {object text:caption_text, position:{70, 154}, width:884, height:44}
			if chart_kind is "pie" then
				add chart s row names row_names column names column_names data chart_data type pie_2d group by chart row
			else if chart_kind is "vbar" then
				add chart s row names row_names column names column_names data chart_data type vertical_bar_2d group by chart row
			else if chart_kind is "hbar" then
				add chart s row names row_names column names column_names data chart_data type horizontal_bar_2d group by chart row
			else if chart_kind is "line" then
				add chart s row names row_names column names column_names data chart_data type line_2d group by chart row
			else
				add chart s row names row_names column names column_names data chart_data type vertical_bar_2d group by chart row
			end if
			set position of last chart to {95, 212}
			set width of last chart to 834
			set height of last chart to 430
		end tell
	end tell
	my style_body_text(cap_box, 18)
	return s
end add_chart_slide

on add_final_asks_slide(doc_ref)
	tell application "Keynote"
		tell doc_ref
			set s to make new slide with properties {base layout:slide layout "Blank"}
		end tell
	end tell
	my add_header_block(s, "Decision Asks and Next Steps")
	tell application "Keynote"
		tell s
			set asks_box to make new text item with properties {object text:my bulletize_lines({"Approve pilot tenant set and success baseline", "Confirm weekly operating cadence for leadership, account, analyst, and ops", "Assign escalation owner for reliability incidents and client communications", "Prioritize next-phase scope: connector expansion + advanced reporting UX"}), position:{70, 178}, width:884, height:320}
			set close_box to make new text item with properties {object text:"Recommended next action: 45-minute cross-functional walkthrough using this deck and live dashboard demo.", position:{70, 550}, width:884, height:96}
		end tell
	end tell
	my style_body_text(asks_box, 24)
	my style_body_text(close_box, 23)
	return s
end add_final_asks_slide

tell application "Keynote"
	activate

	set output_key to POSIX file "/Users/thristannewman/ADinsights/docs/project/adinsights-stakeholder-deck.key"
	set output_pptx to POSIX file "/Users/thristannewman/ADinsights/docs/project/adinsights-stakeholder-deck.pptx"

	set deck to make new document with properties {document theme:theme "White"}
end tell

my add_title_slide(deck)
my add_bullet_slide(deck, "ADinsights Creates One Trusted Decision Layer", {"One source of truth across Meta and Google paid media performance", "Faster reporting through automated ingestion, modeling, and dashboard snapshots", "Higher stakeholder confidence from freshness indicators and runbook-backed operations"})
my add_bullet_slide(deck, "Every Stakeholder Gets Faster Clarity", {"Agency leadership: portfolio visibility and growth confidence", "Account and client success: faster client-ready reporting", "Analysts and media buyers: optimization-ready campaign and creative drill-downs", "Finance and RevOps: standardized spend and outcomes", "Ops and Security: reliable, tenant-safe operations"})
my add_bullet_slide(deck, "Current Reporting Friction Slows Decisions", {"Fragmented channel reporting and manual reconciliation", "Delayed insights for leadership and client reviews", "Inconsistent definitions across teams", "Stale data discovered too late in the reporting cycle"})
my add_flow_graphic_slide(deck, "Automated Data Flow Reduces Reporting Risk", "End-to-end flow from ingestion to stakeholder decisions")
my add_two_column_slide(deck, "Role-Based Value Is Clear and Actionable", "Commercial Stakeholders", {"Leadership: see portfolio health at a glance", "Account leads: prep client reviews faster", "Finance: track spend efficiency and pacing"}, "Delivery Stakeholders", {"Analysts: drill into campaigns and creative performance", "Ops: monitor freshness and sync reliability", "Security: maintain tenant isolation and secrets hygiene"})
my add_chart_slide(deck, "Platform Maturity Is Already Strong", "Current product status across capability areas", {"Capability Areas"}, {"Built", "In Progress", "Planned"}, {{6, 2, 4}}, "pie")
my add_chart_slide(deck, "Reliability Commitments Protect Trust", "SLA and freshness commitments that protect stakeholder trust", {"Target"}, {"Nightly Sync", "dbt Freshness", "Dashboard Freshness"}, {{99, 98, 99}}, "vbar")
my add_chart_slide(deck, "Impact Is Broad Across Stakeholder Groups", "Illustrative value intensity by role", {"Leadership", "Account Leads", "Analysts", "Finance", "Ops"}, {"Value Score"}, {{90}, {88}, {92}, {80}, {86}}, "hbar")
my add_chart_slide(deck, "Adoption Can Scale Within 90 Days", "Planned tenant coverage progression after kickoff", {"Tenant Coverage"}, {"Day 30", "Day 60", "Day 90"}, {{20, 55, 90}}, "line")
my add_bullet_slide(deck, "Key Risks Have Defined Mitigations", {"Data quality regression -> enforced dbt tests and quality checklist", "Snapshot staleness -> freshness alerts plus runbook response", "Connector coverage gaps -> phased roadmap and validation checklist", "Secrets exposure -> encryption, KMS strategy, and log scrubbing"})
my add_final_asks_slide(deck)

tell application "Keynote"
	export deck to output_pptx as Microsoft PowerPoint
	save deck in output_key
	close deck saving no
end tell
