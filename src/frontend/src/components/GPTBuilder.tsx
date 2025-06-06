const GPTBuilder = () => {
    const url = import.meta.env.VITE_GPT_BUILDER_URL as string | undefined;

    if (!url) {
        return <div>No GPT Builder URL configured.</div>;
    }

    return <iframe src={url} style={{ width: "100%", height: "100vh", border: "none" }} title="GPT Builder" />;
};

export default GPTBuilder;
