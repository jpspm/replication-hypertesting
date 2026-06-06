public class simpleTypes {

    static class A {}
    static class B extends A {}
    static class C extends A {}

    public static int test(int secret) {
        int ret;
        A obj;
        if (secret != 0) {
            obj = new B();
            ret = 1;
        } else {
            obj = new C();
            ret = 0;
        }
        return ret;
    }

}
