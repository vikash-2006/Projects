let runningTotal = 0; // Stores the result of calculations
let buffer = "0"; // Represents the current input
let previousOperator = null; // Tracks the last operator pressed

const screen = document.querySelector("#screen-text");

// Function to handle button clicks
function buttonClick(value) {
    if (isNaN(value)) {
        // If the value is not a number, handle it as a symbol
        handleSymbol(value);
    } else {
        // If the value is a number, handle it
        handleNumber(value);
    }
    // Update the screen text with the current buffer
    screen.innerText = buffer;
}

// Function to handle symbols (C, ←, operators, =)
function handleSymbol(symbol) {
    switch (symbol) {
        case "C":
            buffer = "0";
            runningTotal = 0;
            previousOperator = null;
            break;

        case "←":
            if (buffer.length === 1) {
                buffer = "0"; // Reset to "0" if only one character is left
            } else {
                buffer = buffer.slice(0, -1); // Remove the last character
            }
            break;

        case "=":
            if (previousOperator === null) {
                return; // Ignore if no operation is pending
            }
            flushOperation(parseInt(buffer)); // Perform the operation
            previousOperator = null;
            buffer = runningTotal.toString(); // Display the result
            runningTotal = 0; // Reset runningTotal for future calculations
            break;

        case "+":
        case "-":
        case "*":
        case "÷":
            handleMath(symbol);
            break;
    }
}

// Function to handle numbers
function handleNumber(numberString) {
    if (buffer === "0") {
        buffer = numberString; // Replace the initial "0" with the number
    } else {
        buffer += numberString; // Append the number to the buffer
    }
}

// Function to handle math operations
function handleMath(symbol) {
    if (buffer === "0") {
        // Do nothing if buffer is "0"
        return;
    }

    const intBuffer = parseInt(buffer); // Convert buffer to an integer

    if (runningTotal === 0) {
        runningTotal = intBuffer; // Initialize runningTotal
    } else {
        flushOperation(intBuffer); // Perform the previous operation
    }

    previousOperator = symbol; // Store the current operator
    buffer = "0"; // Reset buffer for the next input
}

// Function to perform calculations based on the operator
function flushOperation(intBuffer) {
    if (previousOperator === "+") {
        runningTotal += intBuffer;
    } else if (previousOperator === "-") {
        runningTotal -= intBuffer;
    } else if (previousOperator === "*") {
        runningTotal *= intBuffer;
    } else if (previousOperator === "÷") {
        runningTotal /= intBuffer;
    }
}

// Initialization function to set up event listeners
function init() {
    const buttons = document.querySelectorAll(".calc-button");

    buttons.forEach((button) => {
        button.addEventListener("click", (event) => {
            const value = event.target.getAttribute("data-value"); // Get button's data-value
            buttonClick(value); // Pass the value to buttonClick function
        });
    });
}

// Run the init function when the script loads
init();
