# 🐼 PandaETL

[![Discord](https://dcbadge.vercel.app/api/server/kF7FqH2FwS?style=flat&compact=true)](https://discord.gg/kF7FqH2FwS)
![Version](https://img.shields.io/github/v/release/Sinaptik-AI/panda-etl?include_prereleases&style=flat-square)

PandaETL is an open-source, no-code ETL (Extract, Transform, Load) tool designed to extract and parse data from various document types including PDFs, emails, websites, audio files, and more. With an intuitive interface and powerful backend, PandaETL simplifies the process of data extraction and transformation, making it accessible to users without programming skills.

## ✨ Features

- **📝 No-Code Interface**: Easily set up and manage ETL processes without writing a single line of code.
- **📄 Multi-Document Support**: Extract data from PDFs, emails, websites, audio files, and more.
- **🔧 Customizable Workflows**: Create and customize extraction workflows to fit your specific needs (coming soon).
- **🔗 Extensive Integrations**: Integrate with various data sources and destinations (coming soon).
- **💬 Chat with Documents**: Chat with your documents to retrieve information and answer questions (coming soon).

## 🚀 Getting Started

### 📋 Prerequisites

- Node.js and npm (or yarn)
- Python 3.x
- Conda
- Poetry (Python package manager)

### 🖥️ Project Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/panda-etl.git
   cd panda-etl
   ```

### Frontend Setup

1. Navigate to the frontend directory:

   ```bash
   cd frontend
   ```

2. Install dependencies (including Husky):

   ```bash
   yarn install
   ```

3. Create a `.env` file in the frontend directory with the following:

   ```bash
   NEXT_PUBLIC_API_URL=http://localhost:5328
   ```

   or copy the `.env.example` file to `.env`

4. Run the development server:

   ```bash
   npm run dev
   # or
   yarn dev
   ```

5. Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

### Backend Setup

1. Navigate to the backend directory:

   ```bash
   cd backend
   ```

2. Create and activate a Conda environment:

   ```bash
   conda create -n pandaetl python=3.x
   conda activate pandaetl
   ```

3. Install Poetry within the Conda environment:

   ```bash
   conda install poetry
   ```

4. Install dependencies using Poetry (including pre-commit):

   ```bash
   poetry install
   ```

5. Set up pre-commit hooks:

   ```bash
   poetry run pre-commit install
   ```

6. Create an environment file from the example:

   ```bash
   cp .env.example .env
   ```

7. Apply database migrations:

   ```bash
   poetry run make migrate
   ```

8. Start the backend server:

   ```bash
   poetry run make run
   ```

## 📚 Usage

### 🆕 Creating a New Project

1. Navigate to the "Projects" page.
2. Click on "New Project".
3. Fill in the project details and click "Create".

### ⚙️ Setting Up an Extraction Process

1. Open a project and navigate to the "Processes" tab.
2. Click on "New Process".
3. Follow the steps to configure your extraction process.

### 💬 Chat with Your Documents (Coming Soon)

Stay tuned for our upcoming feature that allows you to chat with your documents, making data retrieval even more interactive and intuitive.

## 🤝 Contributing

We welcome contributions from the community. To contribute:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes and push to your fork.
4. Create a pull request with a detailed description of your changes.

## 📜 License

This project is licensed under the MIT Expat License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

We would like to thank all the contributors and the open-source community for their support.

## 📞 Contact

For any questions or feedback, please open an issue on GitHub.

## Development Setup

This project uses pre-commit hooks in the backend and Husky in the frontend to ensure code quality and consistency.

### Frontend (Husky)

Husky is set up in the frontend to run linting checks before each commit.

To manually run the frontend linting:
