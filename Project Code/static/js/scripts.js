// Example: Show an alert when the form is submitted
document.addEventListener("DOMContentLoaded", () => {
    const forms = document.querySelectorAll("form");
    forms.forEach(form => {
        form.addEventListener("submit", () => {
            alert("Form submitted!");
        });
    });
});
