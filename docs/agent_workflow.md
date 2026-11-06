# Agent coordination

State machine: created → running → waiting_for_approval → approved / rejected. Approved → rolled_back if compensation remains feasible. Exceptions → failed. Restarted running workflows → failed.

Supervisor creates policy and dependencies. Demand produces independent product/location forecasts. Monitoring flags stock positions. Online and offline agents summarize their channel requirements. Warehouse identifies stock available above reservations/safety. Risk flags low safety stock and delayed orders. Allocation consumes shared forecasts and constraints. Logistics estimates shipment costs. Pricing suggests promotion reviews. Supervisor publishes a validated proposal for human approval.

Each execution stores unique ID, run ID, agent name, status, input summary, output, confidence, duration, error and timestamp. Agent messages persist sender, receiver and structured JSON. Individual controls rerun the dependency workflow deliberately; they do not execute an agent with incomplete inputs. The API validates agent IDs. Failure records are retained on the run and supervisor; recommendations from the failed transaction are rolled back.
