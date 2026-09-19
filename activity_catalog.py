"""Curated DEVELOPMENT FIXTURES. Not a professionally reviewed activity library.

Costs are illustrative USD estimates for supplies, or admission for one adult
and one child. Free ideas assume the listed household materials are on hand.
Photos illustrate the idea, not a specific kit, venue, or included product.
"""
from discovery import Activity, KitPreview

def activity(slug, title, summary, image, alt, ages, tags, interests, minutes, setting, cost, materials, steps, supervision, kind="activity"):
    return Activity(slug, slug, title, summary, image, alt, *ages, kind, tuple(tags), tuple(interests), minutes, setting, cost,
        "supplies" if kind == "activity" else "admission for one adult and one child", tuple(materials), tuple(steps), supervision)

ACTIVITIES = (
    activity("little-animal-safari", "Little Animal Safari", "Turn a corner of home into a tiny animal world. Name the animals and invent a story together.", "animals", "Wooden animal figures in warm sunlight", (24,71), ("play","rainy","animals"), ("animals","stories"), 20,"indoor",0,
        ("Large, age-labeled animal toys", "A towel or play mat"), ("Spread out a mat and choose a few animals.", "Take turns making animal sounds and moving the toys.", "Invent a gentle journey home for each animal."), "Stay nearby. Use large intact toys appropriate for your child's age; keep small parts out of reach."),
    activity("colorful-brush-play", "A Little Color Play", "Make big strokes, mix colors, and enjoy the process of painting together.", "paints", "An assortment of colorful paints", (24,95), ("play","rainy","birthday","art"), ("art",),30,"indoor",10,
        ("Age-labeled washable paint", "Large brush", "Paper and table covering"), ("Cover the table and offer two paint colors.", "Make dots, lines, and broad brush strokes.", "Try mixing a little of each color; set the page aside to dry."), "Supervise throughout. Follow the paint age label, prevent ingestion, and wash hands afterward."),
    activity("animal-story-time", "Stories & Animal Sounds", "A cozy picture-book pause with animal sounds, pointing, and plenty of time to turn the pages.", "books", "Wooden animal figures on a stack of books", (6,59), ("play","rainy","skills","stories"), ("animals","stories"),15,"indoor",0,
        ("An age-appropriate board book", "A comfortable place to sit"), ("Sit together and let your child choose a book.", "Point to pictures and name what you see.", "Pause for their sounds, gestures, or questions; finish when they lose interest."), "Stay with your child. Inspect books for loose or torn pieces and keep the seating area secure."),
    activity("a-gentle-zoo-day", "A Gentle Zoo Day", "Choose just a few animals to visit, with breaks for snacks and a slower pace.", "zoo", "Giraffes among trees in a zoo enclosure", (12,95), ("outings","animals"), ("animals","nature"),180,"outdoor",50,
        ("Water and weather-appropriate clothing", "Venue information", "Your usual outing supplies"), ("Check opening hours, accessibility, and actual admission before leaving.", "Choose two or three exhibits and plan rest stops.", "Watch animals from public areas and talk about what you notice."), "Maintain close adult supervision, follow venue rules, and never cross barriers or feed animals without staff direction.","outing"),
    activity("build-a-little-town", "Build a Little Town", "Stack, arrange, and imagine a neighborhood made from large blocks.", "hero", "Child arranging large wooden blocks", (18,71), ("play","skills","rainy","building"), ("building",),30,"indoor",0,
        ("Large age-appropriate blocks", "Clear floor space"), ("Clear a comfortable space on the floor.", "Build a low tower or a small house together.", "Add a road, then take turns changing the town."), "Keep towers low and use blocks without splinters or small detachable pieces. Supervise play."),
    activity("nature-color-walk", "Nature Color Walk", "Find green, brown, and golden things on a familiar walk. Looking is all you need to do.", "zoo", "Green trees in an outdoor animal park", (18,95), ("outings","skills","nature"), ("nature",),30,"outdoor",0,
        ("Comfortable shoes", "Weather-appropriate layers"), ("Pick a short familiar route away from traffic.", "Choose a color and look for it together.", "Stop for a rest and name your favorite discovery."), "Hold hands near roads and water. Observe plants without tasting or collecting unfamiliar items.","outing"),
    activity("rainy-day-rhythm", "Rainy Day Rhythm", "Clap a little rhythm and let your child answer. No instruments needed.", "toys", "Wooden toys arranged on books", (12,71), ("play","rainy","skills","music"), ("music",),15,"indoor",0,
        ("A clear space to sit or stand"), ("Clap twice slowly and pause.", "Invite your child to copy or create their own rhythm.", "Try soft claps and gentle foot taps to a familiar song."), "Keep sound comfortable and movements gentle. Support children who are unsteady and stop if they seem overwhelmed."),
    activity("birthday-story-circle", "Birthday Story Circle", "Make a tiny birthday adventure with a book and a few silly voices.", "books", "Books with wooden animal figures", (24,95), ("play","birthday","rainy","stories"), ("stories","animals"),30,"indoor",0,
        ("A favorite picture book", "Comfortable floor seating"), ("Gather everyone in a small circle.", "Read a short story and invite animal sounds.", "Let each child suggest one happy ending."), "An adult leads the group. Keep walkways clear and let children opt out of performing or joining in."),
    activity("big-paper-birthday", "Big Paper Birthday Art", "Create one big page of joyful marks together for a birthday celebration.", "paints", "Bright paints ready for an art activity", (36,95), ("play","birthday","art"), ("art",),60,"indoor",25,
        ("Large paper", "Age-labeled washable crayons or paint", "Table covering"), ("Cover the table and secure the paper flat.", "Invite everyone to add shapes or colors.", "Let the artwork dry and display it out of reach."), "Supervise materials and follow age labels. Avoid glitter, beads, and loose small decorations."),
    activity("library-picture-hunt", "Library Picture Hunt", "Visit the children's shelves and choose a picture book about something your child loves.", "books", "A small stack of books", (12,95), ("outings","stories"), ("stories",),60,"indoor",0,
        ("Local library opening information"), ("Check hours and accessibility with your library.", "Explore the children's area together.", "Choose a book and settle in for a short read."), "Stay together and respect library rules. This idea is not a live event listing; confirm any sessions directly.","outing"),
    activity("baby-look-and-listen", "Look, Listen, Connect", "A quiet moment together, following your baby's gaze and responding to their sounds.", "books", "Books and simple wooden animal shapes", (0,11), ("play","skills","stories"), ("stories","music"),15,"indoor",0,
        ("A comfortable, secure place to hold your baby"), ("Hold your baby with their head and body supported.", "Speak or sing softly and pause for their response.", "Follow their cues and finish if they turn away or seem tired."), "Stay awake and attentive. This is supervised awake interaction, not a sleep setup. Stop if your baby is uncomfortable."),
    activity("garden-brush-marks", "Garden Brush Marks", "Take paper and a brush outside for a little art in the fresh air.", "paints", "Colorful paints for a supervised art activity", (36,95), ("play","art","nature"), ("art","nature"),30,"outdoor",10,
        ("Paper", "Age-labeled washable paint and a large brush", "Stable outdoor surface"), ("Choose a shaded spot away from roads and water.", "Look at a leaf or flower without picking it.", "Paint the colors or shapes you notice, then bring all materials inside."), "Supervise throughout. Prevent ingestion, follow material age labels, and avoid unfamiliar plants and insects."),
)

class FixtureCatalog:
    def activities(self):
        return ACTIVITIES

KIT_PREVIEWS = (
    KitPreview("little-builders", "Little Builders", "An idea for open-ended stacking, sorting, and small worlds.", "hero", "Wooden blocks used in imaginative play"),
    KitPreview("color-discoverers", "Color Discoverers", "An idea for exploring color and making something all their own.", "paints", "An illustrative selection of colorful paints"),
    KitPreview("animal-adventures", "Animal Adventures", "An idea for animal stories and a little everyday imagination.", "animals", "Illustrative wooden animal figures"),
)
