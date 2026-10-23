**Contains:**
* Architectural reasoning
* Cost analysis
* Routing design

---

## 3.1: Define Five System Scenarios

| Scenario | Description |
| :--- | :--- |
| **Quest Fulfillments** | Standard traffic of daily quest completion. |
| **Evening Rush** | Spike of traffic later in the day due to journal logging and rewards being unlocked. |
| **Journal Breakdowns** | Turning long or emotional journal entries into personalized quests and helpful feedback. |
| **Offline Time** | When a user has weak service or no internet connection. |
| **Server Overload** | Sudden traffic spikes or server crashes that slow down or stop the cloud service. |

---

## 3.2: Design Routing Strategies

| Scenario | Routing Strategy | Local Model Used | Hugging Face Model Used | Expected Benefit |
| :--- | :--- | :--- | :--- | :--- |
| **Quest Fulfillments** | Use tiny local models for quick actions and small cloud models for simple requests. | `HuggingFaceTB/SmolLM2-135M-Instruct` | `Qwen/Qwen2.5-1.5B-Instruct` | Super fast response times and low server bills. |
| **Evening Rush** | Move simple text generation to the device so the servers don’t slow down during busy hours. | `unsloth/Llama-3.2-1B-Instruct` | `tiiuae/Falcon3-3B-Instruct` | Stops app from lagging or crashing when many people log in at once. |
| **Journal Breakdowns** | Send personal, detailed journal entries only to smart cloud models that can handle deep thoughts. | *(None — saved for storage space)* | `microsoft/Phi-4-mini-instruct` <br>**OR**<br> `unsloth/Llama-3.2-3B-Instruct` | Gives high-quality, caring, and safe feedback for personal journal entries. |
| **Offline Time** | Run basic features directly on the device without needing any internet connection. | `HuggingFaceTB/SmolLM2-135M-Instruct` <br>**OR**<br> `Qwen/Qwen2.5-0.5B-Instruct` | *(Not capable — no internet connection)* | Keeps the app working anywhere, even without Wi-Fi or data. |
| **Server Overload** | Stop calling the cloud and let device handle basic app tasks until servers fix themselves. | `unsloth/Llama-3.2-1B-Instruct` | *(Temporarily disabled during cloud crash)* | Keeps the app running safely instead of shutting down or showing error screens. |

---

## Step 3.3: Evaluate the Strategy

