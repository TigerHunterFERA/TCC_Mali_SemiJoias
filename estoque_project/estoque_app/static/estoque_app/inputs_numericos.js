(function () {
    function impedirScrollNoNumero(evento) {
        var campo = evento.target;

        if (
            campo &&
            campo.tagName === "INPUT" &&
            campo.type === "number" &&
            document.activeElement === campo
        ) {
            evento.preventDefault();
        }
    }

    document.addEventListener("wheel", impedirScrollNoNumero, { passive: false });
})();
