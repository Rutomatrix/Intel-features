import { useState, useRef } from "react";
function State() {
    const [count, setCount] = useState(0);
    const countRef = useRef(0);

function incrementState() {
        setCount(count + 1);
    }

function incrementRef() {
    countRef.current += 1;
}
    return (
        <div>
            <h2>useState vs useRef</h2>
            <p>State Count: {count}</p>
            <p>Ref Count: {countRef.current}</p>
            <button onClick={incrementState}>Increment State</button>
            <button onClick={incrementRef}>Increment Ref</button>
        </div>
    );
}
export default State;