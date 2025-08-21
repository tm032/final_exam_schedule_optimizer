// Looping childrens in the HTML parent tag
// https://stackoverflow.com/questions/17094230/how-do-i-loop-through-children-objects-in-javascript

function getExamTimeslotsAsJSON() {
    const timeslots = {};

    for (let i = 1; i <= 4; i++) { // Timeslots
        for (let j = 1; j <= 6; j++) { // Days
            let id = "slot" + j + i;
        
            let slotElement = document.getElementById(id);
            let examElements = slotElement.children;
            timeslots[id] = [];
            for (let k = 0; k < examElements.length; k++) {
                let examElement = examElements[k];
                if (!examElement.classList.contains("details"))
                    timeslots[id].push(examElement.id);
            }
        }
    }
    return JSON.stringify(timeslots)
}


