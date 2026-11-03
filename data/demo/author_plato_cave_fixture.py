"""Author the offline demo fixture for plato_cave (hand-written, NOT model output)."""
import json, sys

def U(kind, label, content, quote, participants=(), basis="explicit", conf=0.9):
    return {"kind": kind, "label": label, "content": content, "participants": list(participants),
            "quote": quote, "basis": basis, "confidence": conf}

def R(target, type_, rationale, conf=0.75, direction="new_to_target"):
    return {"target": target, "type": type_, "direction": direction, "rationale": rationale, "confidence": conf}

def V(target, new_reading, rationale):
    return {"target": target, "new_reading": new_reading, "rationale": rationale}

def D(n, rels=(), revs=(), merge=""):
    return {"new_unit": n, "action": "merge" if merge else "add", "merge_into": merge,
            "relations": list(rels), "revisions": list(revs)}

P, I = {}, {}

# ---- Passage 1 -------------------------------------------------------------
P["p0"] = {"gist": "Socrates sets up an image: prisoners chained in a den since childhood, seeing only shadows cast by a fire.",
 "units": [
  U("situation", "Prisoners chained in a den", "Human beings have lived since childhood in an underground den, chained so they cannot move.",
    "here they have been from their childhood, and have their legs and necks chained so that they cannot move", ["prisoners"]),
  U("image", "Fire behind the prisoners", "A fire burns above and behind the prisoners, with a raised way and a low wall between.",
    "Above and behind them a fire is blazing at a distance", ["fire"]),
  U("image", "Shadows on the wall", "The prisoners see only shadows, of themselves and of carried objects, cast by the fire on the wall.",
    "they see only their own shadows, or the shadows of one another, which the fire throws on the opposite wall of the cave", ["prisoners"]),
  U("claim", "The prisoners are like us", "Socrates says the strange prisoners are like ourselves.",
    "Like ourselves, I replied", ["Socrates", "Glaucon"]),
  U("claim", "Naming shadows as realities", "If they talked, the prisoners would take their words to name what was actually before them.",
    "would they not suppose that they were naming what was actually before them?", ["prisoners"]),
  U("situation", "Unable to turn round", "The chains prevent the prisoners from turning their heads, so they face only one way.",
    "being prevented by the chains from turning round their heads", ["prisoners"]),
 ]}
I["p0"] = {"decisions": [
  D("n1", [R("n4", "RELATES_TO", "The scene of chained prisoners (n1) is immediately said to be 'like ourselves' (n4).", 0.6, "target_to_new")]),
  D("n2", [R("n3", "CAUSES", "The fire 'blazing at a distance' is what 'throws' the shadows on the opposite wall.", 0.9)]),
  D("n3"),
  D("n4"),
  D("n5", [R("n3", "REFINES", "Seeing only shadows becomes a belief: their words would seem to name 'what was actually before them'.", 0.75)]),
  D("n6", [R("n3", "CAUSES", "Being 'prevented by the chains from turning round their heads' is why they 'see only' shadows.", 0.85)]),
]}

# ---- Passage 2 -------------------------------------------------------------
P["p1"] = {"gist": "The prisoners take shadows for truth; a released prisoner is turned toward the light, suffers, and resists being told he saw an illusion.",
 "units": [
  U("claim", "Truth is shadows for them", "For the prisoners, truth would be nothing but the shadows of the images.",
    "To them, I said, the truth would be literally nothing but the shadows of the images.", ["prisoners"]),
  U("event", "Release and painful turning", "A released prisoner is compelled to stand, turn his neck round and look toward the light, and suffers sharp pains.",
    "compelled suddenly to stand up and turn his neck round and walk and look towards the light, he will suffer sharp pains", ["released prisoner"]),
  U("claim", "Shadows still seem truer", "Shown the real objects, the released prisoner would think the shadows truer.",
    "Will he not fancy that the shadows which he formerly saw are truer than the objects which are now shown to him?", ["released prisoner", "instructor"]),
  U("event", "Dragged up the ascent", "He is reluctantly dragged up a steep, rugged ascent into the sunlight.",
    "he is reluctantly dragged up a steep and rugged ascent", ["released prisoner"]),
  U("concept", "Degrees of reality", "What he saw before is called an illusion; turning toward more real existence gives clearer vision.",
    "what he saw before was an illusion, but that now, when he is approaching nearer to being and his eye is turned towards more real existence, he has a clearer vision",
    ["instructor", "released prisoner"], "explicit", 0.85),
 ]}
I["p1"] = {"decisions": [
  D("n1", [R("u00_3", "REFINES", "Passage 1 shows the prisoners seeing only shadows; now those shadows are, for them, the whole of 'the truth'.", 0.85),
           R("u00_5", "SUPPORTS", "Taking words to name 'what was actually before them' (passage 1) is what makes shadows count as truth.", 0.7)]),
  D("n2", [R("u00_6", "REFINES", "The turning the chains once 'prevented' now happens, but it is compelled and painful.", 0.7)]),
  D("n3", [R("n1", "SUPPORTS", "His preferring the shadows as 'truer' shows how firmly shadows had become truth.", 0.75)]),
  D("n4", [R("n2", "REFINES", "The forced turning continues as being 'dragged up a steep and rugged ascent'.", 0.7)]),
  D("n5", [R("n1", "CONTRADICTS", "The instructor calls what he saw 'an illusion', against the prisoners' belief that shadows are the truth.", 0.85),
           R("u00_3", "REFRAMES", "The shadows of passage 1 are no longer just what they see: they are 'an illusion', the lowest grade of what is.", 0.8)],
          [V("u00_3", "The shadows are an illusion: the least real of several grades of being, mistaken for the truth.",
             "The instructor names what was seen before 'an illusion' and contrasts it with 'more real existence'.")]),
]}

# ---- Passage 3 -------------------------------------------------------------
P["p2"] = {"gist": "Outside, the freed prisoner grows accustomed to the light in stages until he can see the sun, reasons about it as cause, and scorns the den's honours.",
 "units": [
  U("concept", "Gradual habituation", "Seeing the upper world requires growing accustomed to it.",
    "He will require to grow accustomed to the sight of the upper world.", ["freed prisoner"]),
  U("claim", "Ordered stages of seeing", "He sees first shadows, then reflections in water, then the objects themselves, then the heavens.",
    "first he will see the shadows best, next the reflections of men and other objects in the water, and then the objects themselves", ["freed prisoner"]),
  U("claim", "The sun as cause of all", "He reasons that the sun governs the seasons and is in a way the cause of all he used to see.",
    "in a certain way the cause of all things which he and his fellows have been accustomed to behold", ["sun", "freed prisoner"]),
  U("situation", "Honours for shadow-watching", "In the den, honours go to those quickest at observing and predicting the passing shadows.",
    "conferring honours among themselves on those who were quickest to observe the passing shadows", ["prisoners"]),
  U("claim", "Rejecting the den's life", "He would endure anything rather than think and live as the prisoners do.",
    "and to endure anything, rather than think as they do and live after their manner", ["freed prisoner"]),
 ]}
I["p2"] = {"decisions": [
  D("n1", [R("u01_2", "REFINES", "The painful turning toward the light (passage 2) becomes a process: one must 'grow accustomed'.", 0.75)]),
  D("n2", [
           R("u00_3", "RELATES_TO", "Shadows reappear as the first, easiest stage of seeing in the upper world.", 0.55)]),
  D("n3"),
  D("n4", [R("u00_5", "REFINES", "Naming shadows (passage 1) turns out to be a social practice, with honours for predicting their sequence.", 0.75)]),
  D("n5", [R("n4", "CONTRADICTS", "The freed prisoner would rather endure anything than share the life the den honours.", 0.8)]),
]}

# ---- Passage 4 -------------------------------------------------------------
P["p3"] = {"gist": "Turning point: Socrates explains the allegory. The den is the visible world, the ascent is the soul's, and the idea of the good is seen last.",
 "units": [
  U("event", "Return into darkness", "Coming back down, his eyes would be full of darkness.",
    "would he not be certain to have his eyes full of darkness?", ["returning prisoner"]),
  U("event", "The liberator would be killed", "Whoever tried to free others and lead them up would be put to death.",
    "if any one tried to loose another and lead him up to the light, let them only catch the offender, and they would put him to death", ["prisoners", "liberator"]),
  U("claim", "The den is the visible world", "Socrates interprets the prison-house as the world of sight and the fire as the sun.",
    "the prison-house is the world of sight, the light of the fire is the sun", ["Socrates"]),
  U("claim", "The ascent is the soul's", "The journey upward is to be read as the soul's ascent into the intellectual world.",
    "interpret the journey upwards to be the ascent of the soul into the intellectual world", ["Socrates", "soul"]),
  U("concept", "The idea of the good", "In the world of knowledge, the idea of the good appears last and only with effort.",
    "in the world of knowledge the idea of good appears last of all, and is seen only with an effort", ["Socrates"]),
  U("claim", "The good guides rational action", "Anyone who would act rationally, in public or private, must fix his eye on the good.",
    "this is the power upon which he who would act rationally either in public or private life must have his eye fixed", ["Socrates"]),
 ]}
I["p3"] = {"decisions": [
  D("n1", [R("u01_2", "RELATES_TO", "Light blinded him going up (passage 2); darkness blinds him coming back down.", 0.55)]),
  D("n2", [R("u02_4", "REFINES", "The den does more than honour shadow-watchers: it would kill anyone who tried to free them.", 0.6)]),
  D("n3", [R("u00_4", "SUPPORTS", "Saying 'like ourselves' (passage 1) is explained: the den is the visible world we all live in.", 0.8)]),
  D("n4", [R("u01_4", "REFRAMES", "Being 'dragged up a steep and rugged ascent' (passage 2) is now the soul's ascent to the intellectual world.", 0.85)],
          [V("u01_4", "The ascent is the soul's movement toward the intellectual world, not a physical climb.",
             "Socrates: 'the journey upwards' is 'the ascent of the soul into the intellectual world'.")]),
  D("n5", [R("u02_3", "REFRAMES", "The sun, 'cause of all things' in passage 3, stands for the good, 'universal author of all things beautiful and right'.", 0.8),
           R("u02_2", "REFINES", "Seeing the sun last (passage 3) matches the good being seen 'last of all'.", 0.75)],
          [V("u02_3", "The sun stands for the idea of the good, the cause of what is right and of truth.",
             "The good is called the 'parent of light and of the lord of light in this visible world'.")]),
  D("n6", [R("n5", "REFINES", "The good is not only known last: it must also guide rational action.", 0.7)]),
]}

# ---- Passage 5 -------------------------------------------------------------
P["p4"] = {"gist": "Those who have seen the good are reluctant to return, and look foolish disputing 'shadows of images of justice'; perplexity has two causes.",
 "units": [
  U("claim", "Reluctance to descend", "Those who attain the vision are unwilling to descend to human affairs.",
    "those who attain to this beatific vision are unwilling to descend to human affairs", ["philosophers"]),
  U("situation", "Courts disputing shadows of justice", "The returned person must fight in courts about images or shadows of images of justice.",
    "compelled to fight in courts of law, or in other places, about the images or the shadows of images of justice", ["returned philosopher"]),
  U("claim", "Two kinds of bewilderment", "Bewilderment of the eyes comes either from leaving the light or from entering it.",
    "the bewilderments of the eyes are of two kinds, and arise from two causes, either from coming out of the light or from going into the light"),
  U("concept", "The mind's eye", "The two bewilderments apply to the mind's eye as much as to the bodily eye.",
    "which is true of the mind's eye, quite as much as of the bodily eye"),
 ]}
I["p4"] = {"decisions": [
  D("n1"),
  D("n2", [R("u00_3", "REFRAMES", "Shadows (passage 1) now include 'shadows of images of justice' that people dispute in court.", 0.85),
           R("u03_1", "SUPPORTS", "The darkness on returning (passage 4) is why he misbehaves 'in a ridiculous manner' in court.", 0.65)],
          [V("u00_3", "Shadows are second-hand appearances that people take for the real thing, including images of justice disputed in courts.",
             "Courts dispute 'the images or the shadows of images of justice' among people 'who have never yet seen absolute justice'.")]),
  D("n3", [R("u03_1", "REFINES", "Eyes 'full of darkness' on return (passage 4) are one of two kinds of bewilderment.", 0.7),
           R("u01_2", "REFINES", "The pain of looking toward the light (passage 2) is the other kind: 'going into the light'.", 0.7)]),
  D("n4", [R("n3", "REFINES", "Extends the two bewilderments from the bodily eye to 'the mind's eye'.", 0.8)]),
]}

# ---- Passage 6 -------------------------------------------------------------
P["p5"] = {"gist": "Education does not put sight into blind eyes; it turns the whole soul, whose capacity to learn is already there, toward being.",
 "units": [
  U("claim", "Education is not insertion", "Some teachers wrongly claim they can put knowledge into a soul like sight into blind eyes.",
    "certain professors of education must be wrong when they say that they can put a knowledge into the soul which was not there before, like sight into blind eyes",
    ["professors of education"]),
  U("claim", "Capacity to learn is innate", "The power and capacity of learning already exists in the soul.",
    "the power and capacity of learning exists in the soul already", ["soul"]),
  U("claim", "Learning as turning the soul", "Knowledge requires turning the whole soul from becoming toward being, as the eye turns only with the whole body.",
    "the instrument of knowledge can only by the movement of the whole soul be turned from the world of becoming into that of being", ["soul"]),
  U("concept", "The art of conversion", "There should be an art of turning the soul, not of implanting sight.",
    "some art which will effect conversion in the easiest and quickest manner"),
  U("claim", "The clever rogue's keen sight", "A clever rogue sees keenly, but his sight serves evil.",
    "his keen eye-sight is forced into the service of evil, and he is mischievous in proportion to his cleverness", ["clever rogue"]),
  U("concept", "The good as highest being", "Learning ends in enduring the sight of the brightest and best of being, the good.",
    "the brightest and best of being, or in other words, of the good"),
 ]}
I["p5"] = {"decisions": [
  D("n1"),
  D("n2", [R("n1", "CONTRADICTS", "If the capacity 'exists in the soul already', education cannot put in knowledge 'which was not there before'.", 0.85)]),
  D("n3", [R("u00_6", "REFRAMES", "Passage 1: the prisoners are 'prevented by the chains from turning round their heads'. Now knowledge comes when the whole soul is 'turned' from becoming to being. Their trouble is direction, not missing sight.", 0.85),
           R("u01_2", "REFRAMES", "Being compelled to 'turn his neck round' toward the light (passage 2) is now a figure for education: turning the whole soul.", 0.8),
           R("u02_1", "REFINES", "'Learn by degrees to endure the sight of being' restates the gradual habituation of passage 3.", 0.6)],
          [V("u00_6", "Not turning shows a soul whose power of sight is intact but faces the wrong way. Education is the turning the chains prevented.",
             "Learning is the soul being 'turned from the world of becoming into that of being'. The faculty of sight 'exists already'."),
           V("u01_2", "The painful forced turning is the model of education: converting the whole soul toward being.",
             "Education is described as an art of 'conversion' that turns the soul around.")]),
  D("n4", [R("n3", "REFINES", "If learning is turning, education should be an 'art' of conversion, not of implanting.", 0.8)]),
  D("n5", [R("n2", "SUPPORTS", "Even the rogue has keen sight, so the faculty is present. What matters is where it is turned.", 0.75)]),
  D("n6", merge="u03_5"),
]}

# ---- Passage 7 -------------------------------------------------------------
P["p6"] = {"gist": "Appetites weigh the soul's vision downward. The founders must compel the best minds to ascend to the good and then make them descend again.",
 "units": [
  U("image", "Leaden weights of pleasure", "Sensual pleasures attached from birth drag the soul down and turn its vision to things below.",
    "which, like leaden weights, were attached to them at their birth, and which drag them down and turn the vision of their souls upon the things that are below",
    ["soul"]),
  U("claim", "Two kinds unfit to rule", "Neither the uneducated nor those who never finish their education make able ministers of State.",
    "neither the uneducated and uninformed of the truth, nor yet those who never make an end of their education, will be able ministers of State"),
  U("claim", "Founders compel the ascent", "The founders of the State must compel the best minds to attain knowledge of the good.",
    "the business of us who are the founders of the State will be to compel the best minds to attain that knowledge", ["founders", "best minds"]),
  U("claim", "Philosophers must descend", "Having seen enough, they must be made to descend again among the prisoners and share their labours.",
    "they must be made to descend again among the prisoners in the den, and partake of their labours and honours", ["philosophers", "prisoners"]),
 ]}
I["p6"] = {"decisions": [
  D("n1", [R("u05_3", "REFINES", "Passage 6 says the soul must be turned. Here is what turns it the wrong way: pleasures that 'turn the vision of their souls upon the things that are below'.", 0.75),
           R("u00_1", "REFRAMES", "The prisoners' chains (passage 1) get an inner counterpart: weights 'attached to them at their birth'.", 0.7)],
          [V("u00_1", "The den is the world of sight, and its chains have an inner counterpart: appetites attached from birth that pull the soul's gaze downward.",
             "Pleasures 'like leaden weights' 'drag them down and turn the vision of their souls' downward.")]),
  D("n2"),
  D("n3", [R("u01_4", "REFINES", "Being 'dragged up' the ascent (passage 2) becomes the founders' policy: to 'compel the best minds'.", 0.75)]),
  D("n4", [R("u04_1", "CONTRADICTS", "Those who see the good are 'unwilling to descend' (passage 5), yet they 'must be made to descend again'.", 0.8),
           R("n2", "RELATES_TO", "Being unfit to rule if education never ends is a reason the educated must descend.", 0.55, "target_to_new")]),
]}

# ---- Passage 8 -------------------------------------------------------------
P["p7"] = {"gist": "Glaucon objects that descent is unjust. Socrates answers that the law aims at the whole State's happiness, so trained rulers must return, and reluctant rulers govern best.",
 "units": [
  U("claim", "Objection: descent is unjust", "Glaucon asks whether it is unjust to give them a worse life when they could have a better one.",
    "ought we to give them a worse life, when they might have a better?", ["Glaucon"]),
  U("claim", "Happiness of the whole State", "The legislator aimed at the happiness of the whole State, not of one class.",
    "the happiness was to be in the whole State", ["legislator"]),
  U("claim", "Habit of seeing in the dark", "Each in turn must go down to the den and get the habit of seeing in the dark.",
    "must go down to the general underground abode, and get the habit of seeing in the dark", ["philosophers"]),
  U("claim", "Returning rulers know the images", "Having seen the good, they will recognise what the images are and what they represent.",
    "you will know what the several images are, and what they represent, because you have seen the beautiful and just and good in their truth", ["philosophers"]),
  U("situation", "Politics as fighting over shadows", "In other States, men fight about shadows and struggle for power as if it were a great good.",
    "in which men fight with one another about shadows only and are distracted in the struggle for power", ["citizens of other States"]),
  U("claim", "Reluctant rulers govern best", "The State whose rulers are most reluctant to govern is the best governed.",
    "the State in which the rulers are most reluctant to govern is always the best and most quietly governed"),
 ]}
I["p7"] = {"decisions": [
  D("n1", [R("u06_4", "CONTRADICTS", "Glaucon challenges the requirement (passage 7) that philosophers 'must be made to descend'.", 0.75)]),
  D("n2", [R("u06_4", "SUPPORTS", "Descent is justified because 'the happiness was to be in the whole State'.", 0.8),
           R("n1", "CONTRADICTS", "Glaucon's objection assumes the goal is the happiness of the philosopher class, which this rejects.", 0.75)]),
  D("n3"),
  D("n4"),
  D("n5", [R("u00_3", "REFRAMES", "Shadows (passage 1) are now what political rivals 'fight with one another about' in 'the struggle for power'.", 0.85),
           R("u04_2", "REFINES", "Courtroom disputes over 'shadows of images of justice' (passage 5) widen into politics as a whole.", 0.75)],
          [V("u00_3", "Shadows are the book's figure for appearances taken as real goods worth fighting for: in perception, in courts and in the struggle for power.",
             "Other States are ones 'in which men fight with one another about shadows only'.")]),
  D("n6"),
]}

# ---- Passage 9 -------------------------------------------------------------
P["p8"] = {"gist": "The educated will accept office as a stern necessity, ruling for virtue and wisdom rather than gold. Only philosophy looks down on political ambition.",
 "units": [
  U("claim", "Office as stern necessity", "Being just, every one of them will take office as a stern necessity.",
    "every one of them will take office as a stern necessity", ["future rulers"]),
  U("claim", "A better life than ruling", "Future rulers need a life better than ruling, or the State will not be well ordered.",
    "You must contrive for your future rulers another and a better life than that of a ruler", ["founders", "future rulers"]),
  U("concept", "True wealth", "True riches are virtue and wisdom, not silver and gold.",
    "they rule who are truly rich, not in silver and gold, but in virtue and wisdom"),
  U("claim", "Philosophy above ambition", "Only true philosophy looks down on the life of political ambition.",
    "the only life which looks down upon the life of political ambition is that of true philosophy"),
 ]}
I["p8"] = {"decisions": [
  D("n1", [R("u07_6", "SUPPORTS", "Taking office only 'as a stern necessity' is the reluctance that, in passage 8, makes the best rulers.", 0.75),
           R("u07_1", "CONTRADICTS", "Glaucon now agrees the commands 'are just', which answers his own objection from passage 8.", 0.7)]),
  D("n2", [R("u07_6", "SUPPORTS", "Rulers stay reluctant only if they have a life better than ruling.", 0.7)]),
  D("n3"),
  D("n4", [R("u02_5", "REFINES", "The freed prisoner's scorn for the den's life (passage 3) is named: philosophy 'looks down upon' political ambition.", 0.7)]),
]}

# ---- Journey (reader-level synthesis over the representation above) ---------
def S(title, summary, first, last, key_units, leads="", bridges=()):
    return {"title": title, "summary": summary, "first_passage": first, "last_passage": last,
            "key_units": list(key_units), "leads_to_next": leads, "bridge_relations": list(bridges)}

JOURNEY = {
 "overview": "Prisoners who mistake shadows for reality are freed and climb toward the sun; the cave turns out to be our own world, education turns out to be a turning of the soul, and those who see most must go back down to govern.",
 "stages": [
  S("Living among shadows", "People chained in a cave take the shadows on the wall for the whole of reality, until one is forced to turn toward the light.",
    1, 2, ["u00_1", "u00_3", "u01_1"],
    "Once one prisoner is turned around, the question becomes how anyone gets from shadows to what is real.", ["r02_1"]),
  S("The slow climb to the sun", "Seeing the real world takes time: first reflections, then things themselves, and at last the sun that makes everything visible.",
    3, 3, ["u02_1", "u02_2", "u02_3"],
    "Socrates then explains what the climb stood for, so the sun and the cave take on new meanings.", ["r03_5", "r03_6"]),
  S("The image explained", "The cave is our everyday world of appearances, the climb is the mind's ascent, and the sun stands for the highest good.",
    4, 5, ["u03_3", "u03_4", "u03_5", "u04_2"],
    "Those who have seen the good would rather stay above, which forces the question of what they owe to those still below.", ["r06_4"]),
  S("Education as turning", "Learning does not put sight into the mind; it turns a power the soul already has toward what is real.",
    6, 7, ["u05_3", "u05_2", "u06_1", "u06_4"],
    "Making philosophers go back down looks unfair to them, so the dialogue must show why it is just.", ["r07_1", "r07_2"]),
  S("The duty to return", "Those who have seen the good must govern, and they rule best precisely because they do not want power.",
    8, 9, ["u07_2", "u07_5", "u07_6", "u08_1"]),
 ],
}

# ---- Journey explanation (cites only candidate refs MOTIF lists: Q per stage, E per transition) ----
def SX(stage, changes, matters, quotes):
    return {"stage": stage, "what_changes": changes, "why_it_matters": matters,
            "quotes": [{"ref": r, "how_it_supports": h} for r, h in quotes]}

def TX(frm, kind, certainty, changes, why, evidence, limitation=""):
    return {"from_stage": frm, "kind": kind, "certainty": certainty, "what_changes": changes, "why": why,
            "evidence": [{"ref": r, "how_it_supports": h} for r, h in evidence], "limitation": limitation}

EXPLAIN = {
 "stages": [
  SX(1, "We meet people who cannot see past appearances and do not know it.",
     "Everything later is measured against this starting point of mistaken belief.",
     [("Q1", "The prisoners have been fixed in place since childhood, so they have never seen otherwise."),
      ("Q3", "For them, shadows are not a part of reality; they are all of it.")]),
  SX(2, "Seeing what is real turns out to be gradual and effortful, ending with the sun as the source of what we see.",
     "It sets up the idea that understanding has levels, and that the highest level explains the rest.",
     [("Q2", "The freed prisoner moves step by step from shadows to reflections to things themselves."),
      ("Q3", "The sun is not just bright; it is the cause of everything he used to see.")]),
  SX(3, "The story becomes an explanation: the cave is our ordinary world and the climb is the mind's.",
     "From here on, every image in the story is also a claim about knowledge and society.",
     [("Q1", "Socrates states outright what the prison and the fire stand for."),
      ("Q2", "The physical climb is reinterpreted as the soul's ascent."),
      ("Q4", "Shadows reappear as disputed images of justice in courts.")]),
  SX(4, "Education is redefined as turning the soul around, not filling it with knowledge.",
     "This explains what the liberation in the story actually was, and why it is hard.",
     [("Q1", "Knowledge needs the whole soul to turn, as the prisoner had to turn his whole body."),
      ("Q2", "The capacity is already there; it only faces the wrong way.")]),
  SX(5, "Those who have turned toward the good must come back and govern.",
     "The journey ends where it began, in the cave, but with a new purpose.",
     [("Q3", "Reluctance to rule becomes a qualification for ruling."),
      ("Q2", "Ordinary politics is described with the image of the shadows.")]),
 ],
 "transitions": [
  TX(1, "development", "supported", "The painful turn toward the light becomes a slow process of getting used to it.",
     "Having shown that release hurts, the text explains how the freed prisoner learns to see.",
     [("E1", "Growing accustomed to the light develops the earlier, painful turning.")]),
  TX(2, "reinterpretation", "supported", "The sun and the climb stop being only parts of a story and become figures for knowledge and the good.",
     "Once the climb is complete, Socrates explains what it meant.",
     [("E1", "The idea of the good takes over the role the sun played as cause of all things."),
      ("E5", "The ascent is re-read as the soul's ascent.")]),
  TX(3, "reinterpretation", "supported", "The prisoners' inability to turn becomes a picture of a soul that faces the wrong way.",
     "To say what education is, the text goes back to the first image and re-reads the chains and the turning.",
     [("E2", "The soul being turned recasts the chains that stopped the prisoners from turning their heads."),
      ("E5", "The forced turning toward the light becomes the model for education.")]),
  TX(4, "contradiction", "supported", "The requirement to return meets an objection that it is unjust, and the answer reshapes it.",
     "Compelling philosophers to descend seems unfair to them, so the text must answer that objection.",
     [("E1", "Glaucon objects to making philosophers descend."),
      ("E2", "The answer appeals to the happiness of the whole State.")]),
 ],
}

out = {
  "_provenance": "HAND-AUTHORED DEMO FIXTURE. Written by a person to exercise the pipeline offline. NOT model output.",
  "book": "plato_cave",
  "perception": P,
  "integration": I,
  "journey": {"plato_cave": JOURNEY},
  "explain": {"plato_cave": EXPLAIN},
}
json.dump(out, open(sys.argv[1], "w"), indent=1, ensure_ascii=False)
print("wrote", sys.argv[1])
