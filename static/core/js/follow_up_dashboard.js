(function () {
    "use strict";

    function getCsrfToken() {

        const name = "csrftoken";

        const cookies =
            document.cookie
                .split(";")
                .map(cookie => cookie.trim());

        for (const cookie of cookies) {

            if (cookie.startsWith(name + "=")) {

                return decodeURIComponent(
                    cookie.substring(name.length + 1)
                );
            }
        }

        return "";
    }


    async function updateFollowUpTaskStatus(
        button
    ) {

        const taskId =
            button.dataset.taskId;

        const newStatus =
            button.dataset.status;


        if (
            !taskId ||
            !newStatus
        ) {
            return;
        }


        button.disabled =
            true;


        const originalText =
            button.textContent;


        button.textContent =
            "در حال ثبت...";


        try {

            const response =
                await fetch(
                    `/api/visits/v1/follow-ups/${encodeURIComponent(
                        taskId
                    )}/status/`,
                    {
                        method: "POST",

                        headers: {
                            "Content-Type":
                                "application/json",

                            "Accept":
                                "application/json",

                            "X-CSRFToken":
                                getCsrfToken()
                        },

                        credentials:
                            "same-origin",

                        body:
                            JSON.stringify({
                                status:
                                    newStatus
                            })
                    }
                );


            const data =
                await response.json();


            if (!response.ok) {

                throw new Error(
                    data.detail ||
                    data.error ||
                    "تغییر وضعیت پیگیری ناموفق بود."
                );
            }


            const card =
                button.closest(
                    ".follow-up-task-card"
                );


            if (card) {

                card.remove();
            }


            window.setTimeout(
                function () {

                    window.location.reload();

                },
                250
            );

        }

        catch (error) {

            alert(
                error.message ||
                "خطا در تغییر وضعیت پیگیری."
            );

            button.disabled =
                false;

            button.textContent =
                originalText;
        }
    }


    document
        .querySelectorAll(
            ".follow-up-action-btn"
        )
        .forEach(
            function (button) {

                button.addEventListener(
                    "click",
                    function () {

                        updateFollowUpTaskStatus(
                            button
                        );
                    }
                );
            }
        );

})();