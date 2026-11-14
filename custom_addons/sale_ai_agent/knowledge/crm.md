# Odoo 20 CRM Playbook

## 1. Core Concepts & Pipelines
- **CRM Leads & Opportunities**: Tracked in `crm.lead`.
- **Stages**: Configured per sales team (`stage_id`) with defined probabilities.
- **Expected Revenue**: Calculated based on expected deal value multiplied by stage probability.

## 2. Tool Execution Sequence
1. Check pipeline health: `get_pipeline_summary()`.
2. Find customer or lead: `search_partner(query)`.
3. Create quotation from opportunity: `create_quotation(partner_name_or_id, items)`.

## 3. Common Errors & Troubleshooting
- **Unassigned Stages**: Ensure leads are assigned to active sales teams and have a valid stage.

