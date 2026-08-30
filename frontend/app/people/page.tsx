import { PeopleDirectory } from "./PeopleDirectory";

export default async function PeoplePage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const params = await searchParams;
  return <PeopleDirectory initialQuery={params.q || ""} />;
}
