module.exports = {
    content: [
        // Percorsi verso i tuoi template Django
        '../../templates/**/*.html',
        '../../**/templates/**/*.html',
    ],
    theme: {
        extend: {},
    },
    plugins: [
        require('daisyui'), // <--- Aggiungi questa riga
    ],
    // Opzionale: configurazione temi daisyUI
    daisyui: {
        themes: ["light", "dark", "cupcake", "nord"],
    },
}