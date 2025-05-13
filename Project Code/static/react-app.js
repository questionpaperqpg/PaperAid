// Get data from Flask template
const year = JSON.parse(document.getElementById('year').textContent);
const branch = JSON.parse(document.getElementById('branch').textContent);
const subject = JSON.parse(document.getElementById('subject').textContent);

// SyllabusViewer Component
const SyllabusViewer = ({ subject, isOpen, onClose }) => {
    const [syllabus, setSyllabus] = React.useState('');

    React.useEffect(() => {
        if (isOpen && subject) {
            fetch('/view_syllabus', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `subject=${encodeURIComponent(subject)}`
            })
            .then(response => response.json())
            .then(data => setSyllabus(data.syllabus))
            .catch(error => console.error('Error:', error));
        }
    }, [isOpen, subject]);

    if (!isOpen) return null;

    return (
        <div className="dialog-overlay">
            <div className="dialog-content">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-xl font-bold">{subject} Syllabus</h2>
                    <button 
                        onClick={onClose}
                        className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
                    >
                        Close
                    </button>
                </div>
                <div 
                    className="prose max-w-none"
                    dangerouslySetInnerHTML={{ __html: syllabus }}
                />
            </div>
        </div>
    );
};

// TopicSelector Component
const TopicSelector = ({ year, subject }) => {
    const [topics, setTopics] = React.useState([]);
    const [selectedTopics, setSelectedTopics] = React.useState([{ topic: '', marks: '' }]);
    const [showSyllabus, setShowSyllabus] = React.useState(false);

    React.useEffect(() => {
        fetch(`/get_topics?subject=${encodeURIComponent(subject)}`)
            .then(response => response.json())
            .then(data => setTopics(data))
            .catch(error => console.error('Error:', error));
    }, [subject]);

    const addTopic = () => {
        setSelectedTopics([...selectedTopics, { topic: '', marks: '' }]);
    };

    const handleTopicChange = (index, value) => {
        const newTopics = [...selectedTopics];
        newTopics[index].topic = value;
        setSelectedTopics(newTopics);
    };

    const handleMarksChange = (index, value) => {
        const newTopics = [...selectedTopics];
        newTopics[index].marks = value;
        setSelectedTopics(newTopics);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('year', year);
        formData.append('subject', subject);
        selectedTopics.forEach((item, index) => {
            formData.append(`topic[]`, item.topic);
            formData.append(`marks[]`, item.marks);
        });

        fetch('/thirdpage', {
            method: 'POST',
            body: formData
        }).then(response => {
            if (response.ok) {
                window.location.href = response.url;
            }
        });
    };

    return (
        <div className="container mx-auto p-6">
            <div className="bg-white shadow-md rounded px-8 pt-6 pb-8 mb-4">
                <h1 className="text-2xl font-bold mb-6">
                    Generating {year} {subject} Question Paper
                </h1>
                
                <button 
                    onClick={() => setShowSyllabus(true)}
                    className="mb-6 bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
                >
                    View Syllabus
                </button>

                <form onSubmit={handleSubmit}>
                    <h3 className="text-xl font-semibold mb-4">Topics:</h3>
                    
                    {selectedTopics.map((item, index) => (
                        <div key={index} className="topic-container">
                            <div className="mb-4">
                                <label className="block text-gray-700 text-sm font-bold mb-2">
                                    Topic:
                                </label>
                                <div className="select-container">
                                    <select
                                        className="custom-select"
                                        value={item.topic}
                                        onChange={(e) => handleTopicChange(index, e.target.value)}
                                        required
                                    >
                                        <option value="">Select a topic</option>
                                        {topics.map((topic) => (
                                            <option key={topic} value={topic}>
                                                {topic}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            
                            <div className="mb-4">
                                <label className="block text-gray-700 text-sm font-bold mb-2">
                                    Marks:
                                </label>
                                <input
                                    type="number"
                                    className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                                    value={item.marks}
                                    onChange={(e) => handleMarksChange(index, e.target.value)}
                                    required
                                    min="1"
                                />
                            </div>
                        </div>
                    ))}

                    <button 
                        type="button" 
                        onClick={addTopic}
                        className="mb-4 bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded mr-2"
                    >
                        Add Another Topic
                    </button>

                    <button 
                        type="submit" 
                        className="bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded"
                    >
                        Next
                    </button>
                </form>

                <SyllabusViewer
                    subject={subject}
                    isOpen={showSyllabus}
                    onClose={() => setShowSyllabus(false)}
                />
            </div>
        </div>
    );
};

// Initialize the React application
ReactDOM.render(
    <TopicSelector year={year} subject={subject} />,
    document.getElementById('root')
);