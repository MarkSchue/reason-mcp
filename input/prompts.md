Just to ensure: My goal is to inject reasoning information into the context of an AI agent. What I am thinking of is an enhancement of the context by injecting things like (as an example):

------
#Rule 1: A car has a weight of 1000.
#Rule 2: A car has a maximum load of 5000kg.
#Rule 3: A pressure below 8.0 is considered low.
....
------

The language model can then take this augmented context into account when making decisions or generating responses.

The rules we inject can also be more complex and include informations about possible causes and effects. This depends on the information that is given within the knowledge base. In case there is a reason or a recommendation, we should also inject it. We also want to provide this in a structured way, so that the language model can easily parse and understand it. For example:

------
#Rule 1: If the weight of the car is above 2000 kg, then the pressure should be above 8.0.  
**Reason:** Heavy loads need higher hydraulic/air pressure to maintain stability and avoid strain on components.  
**Recommendation:** Verify load distribution and, if the weight exceeds 2000 kg, raise the pressure set‑point or inspect the pressure control system.

#Rule 2: If the pressure is below 8.0, then it could be a sign of a leak or a faulty pump.  
**Reason:** Low system pressure usually results from fluid loss or pump inefficiency.  
**Recommendation:** Look for leaks in lines and fittings, test pump operation, and repair or replace defective parts.

#Rule 3: If the weight of the car is above 3000 kg, then it is recommended to check the suspension system.  
**Reason:** Excessive weight places extra stress on springs, dampers and linkages, accelerating wear.  
**Recommendation:** Schedule a suspension inspection, ensure components are rated for the load, and replace worn items.  
....------

What we need in our knowledge base is more information to find the correct rules for a given context. For example, we could have tags or keywords that help us to filter the relevant rules based on the current situation or query of the language model. This is currently not the case and should be foreseen. We also need to ensure that the injected information is concise and relevant, so that it does not overwhelm the language model or consume too much of the context window.