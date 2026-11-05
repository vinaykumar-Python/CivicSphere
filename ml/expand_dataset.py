from pathlib import Path
import pandas as pd

DATA_FILE = Path("ml/data/complaint_training.csv")

# Additional synthetic examples for model development.
# These are illustrative examples, not real citizen complaints.

examples = {
    "garbage": [
        "Garbage bags have been piling up near the apartment entrance for three days.",
        "The municipal waste collection vehicle has not visited our street this week.",
        "Food waste is scattered around the public dustbin and attracting flies.",
        "A garbage collection point is overflowing beside the bus stop.",
        "Household waste has been dumped illegally on the roadside.",
        "The public garbage container is broken and waste is falling onto the road.",
        "Plastic waste is accumulating near the local market.",
        "The waste collection workers skipped our residential area yesterday.",
        "Rotting garbage is creating a foul smell near the park entrance.",
        "The community bin has not been emptied for several days.",
        "Construction debris and household waste are mixed near our building.",
        "Garbage is blocking the entrance to the public walkway.",
        "Waste has been dumped near the school boundary wall.",
        "The street cleaning team left collected garbage on the pavement.",
        "Several public bins are full and need urgent collection.",
        "The roadside dumping area is attracting stray animals.",
        "Waste is scattered around the neighbourhood collection point.",
        "The garbage truck is repeatedly missing our apartment complex.",
        "An illegal waste pile has appeared near the playground.",
        "The market waste collection area needs immediate cleaning.",
    ],
    "roads": [
        "A large pothole has appeared in the middle of our residential road.",
        "The road surface is damaged and vehicles are swerving around it.",
        "A section of the street has broken apart after heavy rain.",
        "The road near the school has deep potholes.",
        "The footpath tiles are broken and difficult for pedestrians to use.",
        "An uncovered road excavation is creating a traffic hazard.",
        "The road repair work has been left incomplete.",
        "A damaged speed breaker is causing problems for vehicles.",
        "The junction surface is uneven and needs resurfacing.",
        "A roadside crater is becoming larger every day.",
        "The pavement is cracked near the public hospital.",
        "Road construction debris is obstructing one lane.",
        "The street surface has sunk near the drainage crossing.",
        "A damaged manhole cover is creating a hazard for motorists.",
        "The road shoulder has collapsed near the residential layout.",
        "The pedestrian pathway is blocked by broken paving stones.",
        "A pothole near the bus stop is causing frequent traffic delays.",
        "The road markings have faded at a busy intersection.",
        "The asphalt has washed away near the roadside.",
        "The damaged road needs inspection and repair.",
    ],
    "streetlights": [
        "The streetlight outside our house has stopped working.",
        "Several streetlights along the main road are not illuminating at night.",
        "The lamp post near the bus shelter flickers continuously.",
        "A streetlight pole is leaning dangerously over the footpath.",
        "The road near the park becomes completely dark after sunset.",
        "The streetlights in our lane have been off for a week.",
        "The light near the pedestrian crossing needs repair.",
        "A damaged streetlight cable is hanging from the pole.",
        "The lamp on the junction pole is broken.",
        "The streetlight near the school gate is not switching on.",
        "Our residential road has insufficient working streetlights.",
        "The public walkway is dark because its lights are faulty.",
        "The streetlight keeps switching off during the night.",
        "A light fixture is broken near the market entrance.",
        "The streetlight pole near the corner is damaged.",
        "The lights on the service road have stopped working.",
        "The streetlight near the crossing is blinking repeatedly.",
        "The lamp post wiring appears exposed.",
        "The streetlight outside the apartment gate needs replacement.",
        "The public road lighting system is not functioning properly.",
    ],
    "water supply": [
        "There has been no water supply to our apartment since yesterday.",
        "Tap water is arriving only for a few minutes each morning.",
        "The drinking water supplied to our building is muddy.",
        "A water pipeline leak is wasting water on the street.",
        "Our neighbourhood has very low water pressure.",
        "The municipal water connection has suddenly stopped working.",
        "Water is leaking continuously from a roadside supply pipe.",
        "The water supply schedule has not been followed this week.",
        "Residents are receiving discoloured water from their taps.",
        "The public water tap is broken and cannot be used.",
        "There is an interruption in the water supply to our street.",
        "The overhead supply line is leaking near the junction.",
        "The water coming from the tap has an unusual smell.",
        "Our building has not received its scheduled water supply.",
        "A damaged water pipe is flooding the roadside.",
        "The public drinking water point needs maintenance.",
        "Water pressure has dropped significantly in our area.",
        "The water connection near our house is leaking.",
        "The neighbourhood water tank is not supplying water.",
        "The water supply problem is affecting several nearby homes.",
    ],
    "drainage": [
        "The roadside drain is overflowing onto the street.",
        "Rainwater is accumulating because the storm drain is blocked.",
        "A clogged drain is causing dirty water to enter our lane.",
        "The drainage cover is broken near the apartment entrance.",
        "Sewage water is flowing across the public footpath.",
        "The roadside drain is emitting a strong unpleasant smell.",
        "Water is stagnant outside our building due to poor drainage.",
        "The stormwater drain is blocked with leaves and plastic.",
        "Drainage water is entering the nearby residential compound.",
        "A sewer line appears to be overflowing near the junction.",
        "The drain has not been cleaned for several weeks.",
        "Rainwater cannot flow because the drainage channel is obstructed.",
        "A damaged drain cover poses a risk to pedestrians.",
        "Wastewater is backing up into the street.",
        "The open drain near the school needs immediate cleaning.",
        "The drainage channel is full of mud and rubbish.",
        "Sewage leakage is creating unsanitary conditions in our area.",
        "The street floods because the storm drain is blocked.",
        "Dirty drainage water is collecting near the market.",
        "The drain outside our house needs repair and desilting.",
    ],
    "public safety": [
        "A fallen electrical wire is lying across the public walkway.",
        "An exposed electrical box is accessible to pedestrians.",
        "A damaged boundary wall may collapse onto the footpath.",
        "An open utility pit is creating a serious public hazard.",
        "A broken railing near the pedestrian bridge needs repair.",
        "A fallen tree is blocking the emergency access road.",
        "A damaged traffic signal is creating confusion at the junction.",
        "A loose metal structure is hanging above the sidewalk.",
        "A dangerous open trench has been left without warning signs.",
        "A damaged public staircase railing may cause injuries.",
        "A large branch is hanging over the busy road.",
        "A missing safety barrier leaves the roadside excavation exposed.",
        "A public playground structure has a sharp broken edge.",
        "The pedestrian crossing signal is not working safely.",
        "A damaged manhole is open and unmarked.",
        "A public building entrance has a dangerously broken step.",
        "A fallen pole is obstructing the emergency vehicle route.",
        "The safety barrier near the road has been damaged.",
        "An unstable signboard is hanging above the pavement.",
        "A hazardous obstruction is blocking the public footpath.",
    ],
    "other": [
        "The public park bench is broken and needs maintenance.",
        "A municipal notice board has been damaged.",
        "The public toilet door is broken and cannot close properly.",
        "The community hall requires general maintenance.",
        "A public seating area has damaged furniture.",
        "The park entrance gate is not closing properly.",
        "The public playground equipment needs routine inspection.",
        "A municipal facility has a damaged notice display.",
        "The public waiting shelter has a broken seat.",
        "A community centre window has been damaged.",
        "The public garden fence needs repair.",
        "The municipal building entrance sign is damaged.",
        "The public convenience facility needs maintenance.",
        "A bench at the bus shelter has become unusable.",
        "The community recreation area needs general repairs.",
        "The public park drinking fountain structure is damaged.",
        "A public information board is no longer readable.",
        "The municipal facility door handle is broken.",
        "The public seating shelter needs maintenance work.",
        "A shared community facility has a damaged entrance gate.",
    ],
}


def main():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATA_FILE}. "
            "Run this script from the project root directory."
        )

    existing = pd.read_csv(DATA_FILE)

    required_columns = {"description", "category"}
    if not required_columns.issubset(existing.columns):
        raise ValueError(
            "The CSV must contain 'description' and 'category' columns."
        )

    existing = existing[["description", "category"]].copy()
    existing["description"] = existing["description"].astype(str).str.strip()
    existing["category"] = existing["category"].astype(str).str.strip().str.lower()

    additions = pd.DataFrame(
        [
            {"description": description, "category": category}
            for category, descriptions in examples.items()
            for description in descriptions
        ]
    )

    combined = pd.concat([existing, additions], ignore_index=True)
    combined["description"] = combined["description"].str.strip()
    combined["category"] = combined["category"].str.strip().str.lower()

    # Remove exact duplicate descriptions so repeated examples
    # do not inflate the dataset size.
    combined = combined.drop_duplicates(
        subset=["description"], keep="first"
    ).reset_index(drop=True)

    combined = combined[
        combined["description"].ne("")
        & combined["category"].ne("")
    ]

    combined.to_csv(DATA_FILE, index=False, encoding="utf-8")

    print("\nCivicCare AI dataset updated successfully.")
    print(f"Dataset file: {DATA_FILE}")
    print(f"Total unique records: {len(combined)}")
    print("\nRecords per category:")
    print(combined["category"].value_counts().sort_index().to_string())
    print("\nNote: These examples are synthetic and require real-world validation.")


if __name__ == "__main__":
    main()
