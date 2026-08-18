function showThinking() {
    const output = document.querySelector("#gpt-output");
    const template = document.querySelector("#thinking-template");

    const clone = template.cloneNode(true);

    clone.id = "";
    clone.classList.remove("hidden");

    output.appendChild(clone);

    return clone;
}


function _cloneAnswerBlock() {
    const output = document.querySelector("#gpt-output");
    const template = document.querySelector("#chat-template");

    const clone = template.cloneNode(true);
    clone.id = "";

    output.appendChild(clone);
    clone.classList.remove("hidden");

    return clone.querySelector(".message");
}


function addToLog(message) {
    const infoBlock = _cloneAnswerBlock();

    if (!infoBlock) {
        console.error("Échec de la création du bloc");
        return null;
    }

    infoBlock.innerText = message;

    return infoBlock;
}


function getChatHistory() {
    const infoBlocks = document.querySelectorAll(
        "#gpt-output .message"
    );

    return Array.from(infoBlocks)
        .map(block => block.innerText)
        .filter(message => message.trim() !== "");
}


async function fetchPromptResponse() {

    const response = await fetch("/prompt", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            messages: getChatHistory()
        })
    });

    if (!response.ok) {
        throw new Error(
            `Erreur serveur : ${response.status}`
        );
    }

    if (!response.body) {
        throw new Error(
            "Le serveur n'a envoyé aucun flux."
        );
    }

    return response.body.getReader();
}


async function readResponseChunks(reader, gptOutput) {

    const decoder = new TextDecoder();
    const converter = new showdown.Converter();

    let chunks = "";

    while (true) {

        const { done, value } = await reader.read();

        if (done) {
            break;
        }

        const text = decoder.decode(value, {
            stream: true
        });

        console.log("Réponse reçue :", text);

        chunks += text;

        gptOutput.innerHTML =
            converter.makeHtml(chunks);
    }

    const remaining = decoder.decode();

    if (remaining) {
        chunks += remaining;
    }

    gptOutput.innerHTML =
        converter.makeHtml(chunks);

    console.log("Réponse complète :", chunks);
}


document.addEventListener("DOMContentLoaded", () => {

    const form = document.querySelector("#prompt-form");
    const promptInput = document.querySelector("#prompt");

    const spinnerIcon =
        document.querySelector("#spinner-icon");

    const sendIcon =
        document.querySelector("#send-icon");


    form.addEventListener("submit", async (event) => {

        event.preventDefault();

        const prompt = promptInput.value.trim();

        if (!prompt) {
            return;
        }


        // Changer l'icône du bouton
        spinnerIcon.classList.remove("hidden");
        sendIcon.classList.add("hidden");


        // Ajouter le message de l'utilisateur
        addToLog(prompt);


        // Vider le champ
        promptInput.value = "";


        let gptOutput = null;
        let thinking = null;


        try {

            // Afficher l'animation
            thinking = showThinking();


            // Envoyer la demande au serveur
            const reader = await fetchPromptResponse();


            // Supprimer l'animation
            thinking.remove();
            thinking = null;


            // Créer le bloc de réponse
            gptOutput = addToLog("");


            // Afficher la réponse progressivement
            await readResponseChunks(
                reader,
                gptOutput
            );


        } catch (error) {

            console.error(
                "Une erreur est survenue :",
                error
            );


            // Supprimer l'animation en cas d'erreur
            if (thinking) {
                thinking.remove();
            }


            // Afficher l'erreur
            if (gptOutput) {

                gptOutput.innerText =
                    "Une erreur est survenue lors de la communication avec le serveur.";

            } else {

                addToLog(
                    "Une erreur est survenue lors de la communication avec le serveur."
                );

            }


        } finally {

            // Remettre le bouton normal
            spinnerIcon.classList.add("hidden");
            sendIcon.classList.remove("hidden");


            // Coloration du code
            hljs.highlightAll();

        }

    });

});