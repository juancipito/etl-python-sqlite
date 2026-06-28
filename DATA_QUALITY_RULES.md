# Data Quality Rules

| Rule | Treatment | Reason |
|---|---|---|
| `transaction_id` is required | Reject missing IDs | A durable key is required for traceability |
| Duplicate transaction IDs | Keep the latest `updated_at`; reject superseded rows | Makes reruns deterministic |
| `customer_name` is required | Reject blank names | Required analytical dimension |
| Transaction date must parse | Reject invalid dates | Prevents false time-series placement |
| Amount must be numeric and greater than zero | Reject invalid values | Avoids invalid aggregates |
| Email must have a basic local@domain.tld structure | Reject invalid values | Demonstrates structural validation |
| Category must map to Software, Hardware, Training, or Support | Reject unknown categories | Produces a controlled vocabulary |
| Status must map to Completed, Pending, or Cancelled | Reject unknown statuses | Produces a controlled vocabulary |
| Missing region | Replace with `Unknown` | Region is optional but missingness remains visible |

## Outputs

- `clean_data.csv`: accepted normalized rows.
- `rejected_data.csv`: rejected source rows with one or more explicit issue codes.
- `synthetic_operations.db`: SQLite tables for clean rows, rejected rows, and quality summary.

The raw file is never modified by the pipeline.
