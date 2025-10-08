from __future__ import annotations

import random
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


app = FastAPI(title="1A2B Game API")


def generate_secret_number() -> str:
    """Generate a 4-digit number with unique digits."""
    digits = random.sample(range(10), 4)
    return "".join(map(str, digits))


def evaluate_guess(secret: str, guess: str) -> Dict[str, int]:
    """Return the 1A2B score for the guess against the secret."""
    count_a = sum(s == g for s, g in zip(secret, guess))
    count_b = sum(g in secret for g in guess) - count_a
    return {"A": count_a, "B": count_b}


class GuessRequest(BaseModel):
    guess: str


@app.on_event("startup")
def startup_event() -> None:
    app.state.secret_number = generate_secret_number()
    app.state.attempts = 0


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>1A2B Game</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 2rem; background: #f9f9f9; }
        h1 { color: #333; }
        #result { margin-top: 1rem; }
        #history { margin-top: 2rem; }
        input[type=\"text\"] { padding: 0.5rem; font-size: 1rem; width: 8rem; }
        button { padding: 0.5rem 1rem; font-size: 1rem; margin-left: 0.5rem; }
        li { margin-bottom: 0.5rem; }
        .won { color: green; font-weight: bold; }
        .error { color: red; }
    </style>
</head>
<body>
    <h1>1A2B Game</h1>
    <p>Enter a 4-digit number with unique digits and press Guess.</p>
    <div>
        <input type=\"text\" id=\"guessInput\" maxlength=\"4\" placeholder=\"1234\" />
        <button id=\"guessButton\">Guess</button>
        <button id=\"resetButton\">New Game</button>
    </div>
    <p id=\"result\"></p>
    <ul id=\"history\"></ul>
    <script>
        const resultEl = document.getElementById('result');
        const historyEl = document.getElementById('history');
        const guessInput = document.getElementById('guessInput');
        const guessButton = document.getElementById('guessButton');
        const resetButton = document.getElementById('resetButton');

        async function sendGuess() {
            const guess = guessInput.value.trim();
            if (guess.length !== 4) {
                resultEl.textContent = 'Please enter a 4-digit number.';
                resultEl.className = 'error';
                return;
            }

            try {
                const response = await fetch('/guess', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ guess })
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.detail || 'Invalid guess');
                }

                const { A, B } = data.result;
                const entry = document.createElement('li');
                entry.textContent = `${guess} → ${A}A${B}B (Attempt ${data.attempts})`;
                historyEl.prepend(entry);

                resultEl.textContent = data.message;
                resultEl.className = data.status === 'won' ? 'won' : '';

                if (data.status === 'won') {
                    guessButton.disabled = true;
                }
            } catch (error) {
                resultEl.textContent = error.message;
                resultEl.className = 'error';
            }
        }

        async function resetGame() {
            const response = await fetch('/reset', { method: 'POST' });
            if (response.ok) {
                resultEl.textContent = 'New game started!';
                resultEl.className = '';
                historyEl.innerHTML = '';
                guessInput.value = '';
                guessButton.disabled = false;
                guessInput.focus();
            } else {
                resultEl.textContent = 'Unable to reset game.';
                resultEl.className = 'error';
            }
        }

        guessButton.addEventListener('click', sendGuess);
        resetButton.addEventListener('click', resetGame);
        guessInput.addEventListener('keyup', (event) => {
            if (event.key === 'Enter') {
                sendGuess();
            }
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def get_home() -> str:
    """Return the HTML page for the 1A2B game."""
    return HTML_TEMPLATE


@app.post("/guess")
def post_guess(payload: GuessRequest) -> Dict[str, object]:
    guess = payload.guess
    if not guess.isdigit() or len(guess) != 4:
        raise HTTPException(status_code=400, detail="Guess must be a 4-digit number.")
    if len(set(guess)) != 4:
        raise HTTPException(status_code=400, detail="Digits must be unique.")

    secret_number = app.state.secret_number
    result = evaluate_guess(secret_number, guess)
    app.state.attempts += 1
    attempt_number = app.state.attempts

    status = "won" if result["A"] == 4 else "continue"
    message = "Congratulations! You guessed the correct number." if status == "won" else "Keep trying!"

    if status == "won":
        app.state.secret_number = generate_secret_number()
        app.state.attempts = 0

    return {
        "guess": guess,
        "result": result,
        "attempts": attempt_number,
        "status": status,
        "message": message,
    }


@app.post("/reset")
def reset_game() -> Dict[str, str]:
    app.state.secret_number = generate_secret_number()
    app.state.attempts = 0
    return {"status": "reset", "message": "A new game has started."}
